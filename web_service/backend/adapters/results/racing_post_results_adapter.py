from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone
import re
import asyncio
from selectolax.parser import HTMLParser, Node

from .base import (
    PageFetchingResultsAdapter,
    parse_currency_value,
    parse_fractional_odds,
    build_start_time,
    _BET_ALIASES,
    _extract_race_number_from_text
)
from ...models import ResultRace, ResultRunner
from ...utils.text import normalize_venue_name, clean_text
from ...core.smart_fetcher import FetchStrategy, BrowserEngine
import fortuna


class RacingPostResultsAdapter(PageFetchingResultsAdapter):
    """Racing Post results — UK / IRE thoroughbred and jumps."""

    SOURCE_NAME = "RacingPostResults"
    BASE_URL    = "https://www.racingpost.com"
    HOST        = "www.racingpost.com"
    IMPERSONATE = "chrome120"
    TIMEOUT     = 60

    def _configure_fetch_strategy(self) -> FetchStrategy:
        strategy = super()._configure_fetch_strategy()
        # RacingPost is JS-heavy and has strong bot detection; keep CURL_CFFI primary but ensure fallback (Project Hardening)
        strategy.primary_engine = BrowserEngine.CURL_CFFI
        return strategy

    # -- link discovery ----------------------------------------------------

    async def _discover_result_links(self, date_str: str) -> Set[str]:
        resp = await self.make_request(
            "GET", f"/results/{date_str}", headers=self._get_headers(),
        )
        if not resp or not resp.text:
            return set()

        if self._check_for_block(resp.text, f"/results/{date_str}"):
            return set()

        self._save_debug_snapshot(resp.text, f"rp_results_index_{date_str}")
        parser = HTMLParser(resp.text)
        return self._extract_rp_links(parser)

    def _extract_rp_links(self, parser: HTMLParser) -> set:
        links: set = set()

        _SELECTORS = [
            'a[data-test-selector="RC-meetingItem__link_race"]',
            'a[href*="/results/"]',
            ".ui-link.rp-raceCourse__panel__race__time",
            "a.rp-raceCourse__panel__race__time",
            ".rp-raceCourse__panel__race__time a",
            ".RC-meetingItem__link",
        ]
        for selector in _SELECTORS:
            for a in parser.css(selector):
                href = a.attributes.get("href", "")
                if not href:
                    continue
                if not self._venue_matches(a.text(), href):
                    continue
                if self._is_rp_race_link(href):
                    links.add(href)

        # Last-resort fallback
        if not links:
            for a in parser.css('a[href*="/results/"]'):
                href = a.attributes.get("href", "")
                if len(href.split("/")) >= 3:
                    links.add(href)

        return links

    @staticmethod
    def _is_rp_race_link(href: str) -> bool:
        return bool(
            re.search(r"/results/.*?\d{5,}", href)
            or re.search(r"/results/\d+/", href)
            or re.search(r"/\d{4}-\d{2}-\d{2}/", href)
            or ("/results/" in href and len(href.split("/")) >= 4)
        )

    # -- single-race page parsing ------------------------------------------

    def _parse_race_page(
        self, html: str, date_str: str, _url: str,
    ) -> Optional[ResultRace]:
        parser = HTMLParser(html)

        venue_node = parser.css_first(".rp-raceTimeCourseName__course")
        if not venue_node:
            return None
        venue = normalize_venue_name(venue_node.text(strip=True))

        dividends = self._parse_tote_dividends(parser)
        trifecta_pay, trifecta_combo = self._exotic_from_dividends(
            dividends, "trifecta",
        )
        superfecta_pay, superfecta_combo = self._exotic_from_dividends(
            dividends, "superfecta",
        )

        race_num = self._extract_rp_race_number(parser)

        runners = self._parse_rp_runners(parser, dividends)
        if not runners:
            return None

        return ResultRace(
            id=self._make_race_id("rp_res", venue, date_str, race_num),
            venue=venue,
            race_number=race_num,
            start_time=build_start_time(date_str),
            runners=runners,
            source=self.SOURCE_NAME,
            trifecta_payout=trifecta_pay,
            trifecta_combination=trifecta_combo,
            superfecta_payout=superfecta_pay,
            superfecta_combination=superfecta_combo,
            official_dividends={
                k: parse_currency_value(v) for k, v in dividends.items()
            },
        )

    # -- RP-specific helpers -----------------------------------------------

    @staticmethod
    def _parse_tote_dividends(parser: HTMLParser) -> Dict[str, str]:
        """Extract label→value pairs from the Tote Returns panel."""
        container = (
            parser.css_first('div[data-test-selector="RC-toteReturns"]')
            or parser.css_first(".rp-toteReturns")
        )
        if not container:
            return {}

        dividends: Dict[str, str] = {}
        for row in (
            container.css("div.rp-toteReturns__row")
            or container.css(".rp-toteReturns__row")
        ):
            label_node = (
                row.css_first("div.rp-toteReturns__label")
                or row.css_first(".rp-toteReturns__label")
            )
            val_node = (
                row.css_first("div.rp-toteReturns__value")
                or row.css_first(".rp-toteReturns__value")
            )
            if label_node and val_node:
                label = clean_text(label_node.text())
                value = clean_text(val_node.text())
                if label and value:
                    dividends[label] = value
        return dividends

    @staticmethod
    def _exotic_from_dividends(
        dividends: Dict[str, str],
        bet_type: str,
    ) -> Tuple[Optional[float], Optional[str]]:
        aliases = _BET_ALIASES.get(bet_type, [bet_type])
        for label, val in dividends.items():
            if any(a in label.lower() for a in aliases):
                payout = parse_currency_value(val)
                combo = (
                    val.split("£")[-1].strip() if "£" in val else None
                )
                return payout, combo
        return None, None

    @staticmethod
    def _extract_rp_race_number(parser: HTMLParser) -> int:
        # Priority 1 — navigation bar active item
        for i, link in enumerate(
            parser.css('a[data-test-selector="RC-raceTime"]'),
        ):
            cls = link.attributes.get("class", "")
            if "active" in cls or "rp-raceTimeCourseName__time" in cls:
                return i + 1
        # Priority 2 — text fallback
        return _extract_race_number_from_text(parser) or 1

    def _parse_rp_runners(
        self,
        parser: HTMLParser,
        dividends: Dict[str, str],
    ) -> List[ResultRunner]:
        runners: List[ResultRunner] = []
        for row in parser.css(".rp-horseTable__table__row"):
            try:
                name_node = row.css_first(".rp-horseTable__horse__name")
                if not name_node:
                    continue
                name = clean_text(name_node.text())

                pos_node = row.css_first(".rp-horseTable__pos__number")
                pos = (
                    clean_text(pos_node.text()) if pos_node else None
                )

                num_node = row.css_first(".rp-horseTable__saddleClothNo")
                number = 0
                if num_node:
                    try:
                        number = int(clean_text(num_node.text()))
                    except ValueError:
                        pass

                # Place payout from dividends map
                place_payout: Optional[float] = None
                for lbl, val in dividends.items():
                    if (
                        "place" in lbl.lower()
                        and name.lower() in lbl.lower()
                    ):
                        place_payout = parse_currency_value(val)
                        break

                sp_node = row.css_first(".rp-horseTable__horse__sp")
                final_odds = 0.0
                if sp_node:
                    final_odds = parse_fractional_odds(
                        clean_text(sp_node.text()),
                    )

                runners.append(ResultRunner(
                    name=name,
                    number=number,
                    position=pos,
                    place_payout=place_payout,
                    final_win_odds=final_odds,
                ))
            except Exception:
                continue
        return runners
