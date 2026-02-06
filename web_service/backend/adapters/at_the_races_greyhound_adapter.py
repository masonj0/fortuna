# python_service/adapters/at_the_races_greyhound_adapter.py
"""Adapter for AtTheRaces Greyhound racing."""

import asyncio
import json
import re
import html
from datetime import datetime, timezone
from typing import Any, List, Optional, Dict

from selectolax.parser import HTMLParser

from ..models import Race, Runner, OddsData
from ..utils.odds import parse_odds_to_decimal, SmartOddsExtractor
from ..utils.text import clean_text, normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3
from .mixins import BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin, JSONParsingMixin
from .utils.odds_validator import create_odds_data
from ..core.smart_fetcher import BrowserEngine, FetchStrategy


class AtTheRacesGreyhoundAdapter(JSONParsingMixin, BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin, BaseAdapterV3):
    """
    Adapter for greyhounds.attheraces.com.

    This site is a modern SPA with data embedded in JSON-LD and HTML attributes.
    Uses simple HTTP requests as the data is available in the initial HTML.
    """

    SOURCE_NAME = "AtTheRacesGreyhound"
    BASE_URL = "https://greyhounds.attheraces.com"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config
        )
        self._semaphore = asyncio.Semaphore(5)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """Greyhounds ATR is a modern site but data is in HTML - PLAYWRIGHT works best for SPAs."""
        return FetchStrategy(primary_engine=BrowserEngine.PLAYWRIGHT, enable_js=True, stealth_mode="fast", timeout=45)

    def _get_headers(self) -> dict:
        """Get headers for ATR Greyhound requests."""
        return self._get_browser_headers(
            host="greyhounds.attheraces.com",
            referer="https://greyhounds.attheraces.com/racecards",
        )

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        index_url = f"/racecards/{date}" if date else "/racecards"
        resp = await self.make_request("GET", index_url, headers=self._get_headers())
        if not resp:
            return None
        self._save_debug_snapshot(resp.text, f"atr_grey_index_{date}")
        parser = HTMLParser(resp.text)
        metadata = self._extract_race_metadata_enhanced(parser)
        if not metadata:
            links = []
            scripts = self._parse_all_jsons_from_scripts(parser, 'script[type="application/ld+json"]', context="ATR Greyhound Index")
            for d in scripts:
                items = d.get("@graph", [d]) if isinstance(d, dict) else []
                for item in items:
                    if item.get("@type") == "SportsEvent":
                        loc = item.get("location")
                        if isinstance(loc, list):
                            for l in loc:
                                if u := l.get("url"): links.append(u)
                        elif isinstance(loc, dict):
                            if u := loc.get("url"): links.append(u)
            metadata = [{"url": l, "race_number": 0} for l in set(links)]
        if not metadata:
            return None
        pages = await self._fetch_race_pages_concurrent(metadata, self._get_headers(), semaphore_limit=5)
        return {"pages": pages, "date": date}

    def _extract_race_metadata_enhanced(self, parser: HTMLParser) -> List[Dict[str, Any]]:
        meta: List[Dict[str, Any]] = []
        pc = parser.css_first("page-content")
        if not pc:
            return []
        items_raw = pc.attributes.get(":items") or pc.attributes.get(":modules")
        if not items_raw:
            return []
        try:
            modules = json.loads(html.unescape(items_raw))
            for module in modules:
                for meeting in module.get("data", {}).get("items", []):
                    for i, race in enumerate(meeting.get("items", [])):
                        if race.get("type") == "racecard":
                            r_num = race.get("raceNumber") or race.get("number") or (i + 1)
                            if u := race.get("cta", {}).get("href"):
                                meta.append({"url": u, "race_number": r_num})
        except:
            pass
        return meta

    def _parse_races(self, raw_data: Any) -> List[Race]:
        if not raw_data or not raw_data.get("pages"):
            return []
        try:
            race_date = datetime.strptime(raw_data.get("date", ""), "%Y-%m-%d").date()
        except:
            race_date = datetime.now(timezone.utc).date()
        races: List[Race] = []
        for item in raw_data["pages"]:
            if not item or not item.get("html"):
                continue
            try:
                race = self._parse_single_race_enhanced(item["html"], item.get("url", ""), race_date, item.get("race_number"))
                if race:
                    races.append(race)
            except:
                pass
        return races

    def _parse_single_race_enhanced(self, html_content: str, url_path: str, race_date, race_number: Optional[int]) -> Optional[Race]:
        """Parse a single greyhound race from HTML content."""
        parser = HTMLParser(html_content)
        pc = parser.css_first("page-content")
        if not pc:
            return None
        items_raw = pc.attributes.get(":items") or pc.attributes.get(":modules")
        if not items_raw:
            return None
        try:
            modules = json.loads(html.unescape(items_raw))
        except:
            return None
        venue, race_time_str, distance, runners, odds_map = "", "", "", [], {}
        for module in modules:
            m_type, m_data = module.get("type"), module.get("data", {})
            if m_type == "RacecardHero":
                venue = normalize_venue_name(m_data.get("track", ""))
                race_time_str = m_data.get("time", "")
                distance = m_data.get("distance", "")
                if not race_number:
                    race_number = m_data.get("raceNumber") or m_data.get("number")
            if m_type == "OddsGrid":
                odds_grid = m_data.get("oddsGrid", {})
                partners = odds_grid.get("partners", {})
                all_partners = []
                if isinstance(partners, dict):
                    for p_list in partners.values(): all_partners.extend(p_list)
                elif isinstance(partners, list):
                    all_partners = partners
                for partner in all_partners:
                    for o in partner.get("odds", []):
                        g_id = o.get("betParams", {}).get("greyhoundId")
                        price = o.get("value", {}).get("decimal")
                        if g_id and price:
                            try:
                                p_val = float(price)
                                if p_val > 0: odds_map[str(g_id)] = p_val
                            except: pass
                for t in odds_grid.get("traps", []):
                    trap_num = t.get("trap", 0)
                    name = clean_text(t.get("name", "")) or ""
                    g_id_match = re.search(r"/greyhound/(\d+)", t.get("href", ""))
                    g_id = g_id_match.group(1) if g_id_match else None
                    win_odds = odds_map.get(str(g_id)) if g_id else None

                    # Advanced heuristic fallback
                    if win_odds is None:
                        win_odds = SmartOddsExtractor.extract_from_text(str(t))

                    odds_data = {}
                    if win_odds:
                        odds_data[self.SOURCE_NAME] = OddsData(win=win_odds, source=self.SOURCE_NAME, last_updated=datetime.now(timezone.utc))
                    runners.append(Runner(number=trap_num or 0, name=name, odds=odds_data))
        if not venue or not runners:
            url_parts = url_path.split("/")
            if len(url_parts) >= 5:
                venue = normalize_venue_name(url_parts[3])
                race_time_str = url_parts[-1]
        if not venue or not runners:
            return None
        try:
            if ":" not in race_time_str and len(race_time_str) == 4:
                race_time_str = f"{race_time_str[:2]}:{race_time_str[2:]}"
            start_time = datetime.combine(race_date, datetime.strptime(race_time_str, "%H:%M").time())
            start_time = start_time.replace(tzinfo=timezone.utc)
        except:
            return None

        # Capture available bets
        available_bets = []
        html_lower = html_content.lower()
        for kw in ["superfecta", "trifecta", "exacta", "quinella"]:
            if kw in html_lower:
                available_bets.append(kw.capitalize())

        return Race(
            discipline="Greyhound",
            id=f"atrg_{venue.lower().replace(' ', '')}_{start_time:%Y%m%d_%H%M}",
            venue=venue,
            race_number=race_number or 0,
            start_time=start_time,
            runners=runners,
            distance=str(distance) if distance else None,
            source=self.SOURCE_NAME,
            metadata={"available_bets": available_bets}
        )
