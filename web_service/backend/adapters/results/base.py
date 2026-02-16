from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Final, List, Optional, Set, Tuple, Type
from zoneinfo import ZoneInfo

import structlog
from selectolax.parser import HTMLParser, Node

from ..base_adapter_v3 import BaseAdapterV3
from ..mixins import BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin
from ...models import ResultRace, ResultRunner
from ...utils.text import normalize_venue_name, clean_text
from ...utils.odds import parse_odds_to_decimal
from ...core.smart_fetcher import FetchStrategy, BrowserEngine

EASTERN = ZoneInfo("America/New_York")

def parse_currency_value(value_str: str) -> float:
    """'$1,234.56' -> 1234.56"""
    if not value_str:
        return 0.0
    try:
        raw = str(value_str).strip()
        # Allow standard currency symbols and codes (GBP, EUR, USD, ZAR)
        if re.search(r"[^\d.,$£€\sA-Z]", raw):
            return 0.0

        if "," in raw and "." in raw:
            if raw.rfind(",") > raw.rfind("."):
                # European style: 1.234,56
                cleaned = raw.replace(".", "").replace(",", ".")
            else:
                # US style: 1,234.56
                cleaned = raw.replace(",", "")
        elif "," in raw and "." not in raw and re.search(r",\d{2}$", raw):
            # European format: 12,34
            cleaned = raw.replace(",", ".")
        else:
            cleaned = raw.replace(",", "")

        cleaned = re.sub(r"[^\d.]", "", cleaned)
        return float(cleaned) if cleaned else 0.0
    except (ValueError, TypeError):
        return 0.0


def parse_fractional_odds(text: str) -> float:
    """'5/2' -> 3.5, '2.5' -> 2.5, anything else -> 0.0."""
    val = parse_odds_to_decimal(text)
    return float(val) if val is not None else 0.0


def build_start_time(
    date_str: str,
    time_str: Optional[str] = None,
    *,
    tz: ZoneInfo = EASTERN,
) -> datetime:
    """Build a tz-aware datetime from YYYY-MM-DD + optional HH:MM."""
    try:
        base = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        structlog.get_logger("build_start_time").warning("unparseable_date", date=date_str)
        base = datetime.now(tz)
    hour, minute = 12, 0
    if time_str:
        try:
            parts = time_str.strip().split(":")
            hour, minute = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            structlog.get_logger("build_start_time").warning("malformed_time_string", time=time_str)
            pass
    return base.replace(hour=hour, minute=minute, tzinfo=tz)


def find_nested_value(
    obj: Any,
    key_fragment: str,
    *,
    _depth: int = 0,
    _max_depth: int = 20,
) -> Optional[float]:
    """Recursively search dicts/lists for a key containing key_fragment
    whose value is numeric. Depth-guarded."""
    if _depth > _max_depth:
        return None
    frag = key_fragment.lower()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if frag in k.lower() and isinstance(v, (int, float, str)):
                parsed = (
                    parse_currency_value(str(v))
                    if isinstance(v, str)
                    else float(v)
                )
                if parsed:
                    return parsed
            found = find_nested_value(
                v, key_fragment, _depth=_depth + 1, _max_depth=_max_depth,
            )
            if found is not None:
                return found
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            found = find_nested_value(
                item, key_fragment, _depth=_depth + 1, _max_depth=_max_depth,
            )
            if found is not None:
                return found
    return None


_BET_ALIASES: Final[Dict[str, List[str]]] = {
    "superfecta": ["superfecta", "first 4", "first four"],
    "trifecta":   ["trifecta", "tricast"],
    "exacta":     ["exacta", "forecast"],
}


def extract_exotic_payouts(
    tables: list[Node],
) -> Dict[str, Tuple[Optional[float], Optional[str]]]:
    """Scan tables for exotic-bet dividend rows."""
    results: Dict[str, Tuple[Optional[float], Optional[str]]] = {}
    for table in tables:
        text = table.text().lower()
        for bet_type, aliases in _BET_ALIASES.items():
            if bet_type in results:
                continue
            if not any(a in text for a in aliases):
                continue
            for row in table.css("tr"):
                row_text = row.text().lower()
                if not any(a in row_text for a in aliases):
                    continue
                cols = row.css("td")
                combo: Optional[str] = None
                payout = 0.0
                if len(cols) >= 3:
                    combo  = clean_text(cols[1].text())
                    payout = parse_currency_value(cols[2].text())
                elif len(cols) >= 2:
                    combo  = clean_text(cols[0].text())
                    payout = parse_currency_value(cols[1].text())
                if payout > 0:
                    results[bet_type] = (payout, combo)
                    break
    return results


def _extract_race_number_from_text(
    parser: HTMLParser,
    url: str = "",
) -> Optional[int]:
    """Best-effort race-number from page text or URL."""
    m = re.search(r"Race\s+(\d+)", parser.text(), re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"/R(\d+)(?:[/?#]|$)", url)
    if m:
        return int(m.group(1))
    return None


class PageFetchingResultsAdapter(
    BrowserHeadersMixin,
    DebugMixin,
    RacePageFetcherMixin,
    BaseAdapterV3,
):
    """Common base for results adapters."""

    ADAPTER_TYPE: Final[str] = "results"

    _BLOCK_SIGNATURES = [
        "pardon our interruption",
        "checking your browser",
        "cloudflare",
        "access denied",
        "captcha",
        "please verify",
    ]

    def _check_for_block(self, html: str, url: str) -> bool:
        lower = html.lower()
        for sig in self._BLOCK_SIGNATURES:
            if sig in lower and len(html) < 10000:
                self.logger.error(
                    "BOT BLOCKED",
                    source=self.source_name,
                    url=url,
                    signature=sig,
                    html_length=len(html),
                )
                return True
        return False

    # -- subclass must set -------------------------------------------------
    SOURCE_NAME: str
    BASE_URL: str
    HOST: str

    # -- subclass may override ---------------------------------------------
    TIMEOUT: int = 60
    IMPERSONATE: Optional[str] = None

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            **kwargs,
        )
        self._target_venues: Optional[Set[str]] = None

    @property
    def target_venues(self) -> Optional[Set[str]]:
        return self._target_venues

    @target_venues.setter
    def target_venues(self, value: Optional[Set[str]]) -> None:
        self._target_venues = value

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(
            primary_engine=BrowserEngine.CURL_CFFI,
            enable_js=True,
            stealth_mode="camouflage",
            timeout=self.TIMEOUT,
        )

    async def make_request(
        self, method: str, url: str, **kwargs: Any,
    ) -> Any:
        if self.IMPERSONATE:
            kwargs.setdefault("impersonate", self.IMPERSONATE)
        return await super().make_request(method, url, **kwargs)

    def _get_headers(self) -> dict:
        return self._get_browser_headers(host=self.HOST)

    def _validate_and_parse_races(self, raw_data: Any) -> List[ResultRace]:
        return self._parse_races(raw_data)

    async def _fetch_data(
        self, date_str: str,
    ) -> Optional[Dict[str, Any]]:
        links = await self._discover_result_links(date_str)
        if not links:
            self.logger.warning(
                "No result links found",
                source=self.source_name,
                date=date_str,
            )
            return None
        return await self._fetch_link_pages(links, date_str)

    async def _discover_result_links(self, date_str: str) -> Set[str]:
        raise NotImplementedError

    async def _fetch_link_pages(
        self, links: Set[str], date_str: str,
    ) -> Optional[Dict[str, Any]]:
        absolute = list(dict.fromkeys(
            lnk if lnk.startswith("http") else f"{self.BASE_URL}{lnk}"
            for lnk in links
        ))
        self.logger.info(
            "Fetching result pages",
            source=self.source_name,
            count=len(absolute),
        )
        metadata = [{"url": u, "race_number": 0} for u in absolute]
        pages = await self._fetch_race_pages_concurrent(
            metadata, self._get_headers(),
        )
        return {"pages": pages, "date": date_str}

    def _parse_races(self, raw_data: Any) -> List[ResultRace]:
        if not raw_data:
            return []
        date_str = raw_data.get(
            "date", datetime.now(EASTERN).strftime("%Y-%m-%d"),
        )
        races: List[ResultRace] = []
        for item in raw_data.get("pages", []):
            html = item.get("html") if isinstance(item, dict) else None
            url  = item.get("url", "") if isinstance(item, dict) else ""
            if not html:
                continue

            if self._check_for_block(html, url):
                continue

            try:
                races.extend(self._parse_page(html, date_str, url))
            except Exception as exc:
                self.logger.warning(
                    "Failed to parse result page",
                    source=self.source_name,
                    url=url,
                    error=str(exc),
                )
        return races

    def _parse_page(
        self, html: str, date_str: str, url: str,
    ) -> List[ResultRace]:
        race = self._parse_race_page(html, date_str, url)
        return [race] if race else []

    def _parse_race_page(
        self, html: str, date_str: str, _url: str,
    ) -> Optional[ResultRace]:
        raise NotImplementedError

    def _venue_matches(self, text: str, href: str = "") -> bool:
        if not self.target_venues:
            return True

        from ...models import get_canonical_venue
        canon_text = get_canonical_venue(text)
        if canon_text != "" and canon_text in self.target_venues:
            return True

        href_clean = href.lower().replace("-", "").replace("_", "")
        for v in self.target_venues:
            if v and v in href_clean:
                return True

        return False

    def _make_race_id(
        self,
        prefix: str,
        venue: str,
        date_str: str,
        race_num: int,
    ) -> str:
        from ...models import get_canonical_venue
        canon = get_canonical_venue(venue)
        return f"{prefix}_{canon}_{date_str.replace('-', '')}_R{race_num}"
