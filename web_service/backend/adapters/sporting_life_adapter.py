# python_service/adapters/sporting_life_adapter.py

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, List, Optional, Dict

from selectolax.parser import HTMLParser, Node

from ..models import Race, Runner, OddsData
from ..utils.odds import parse_odds_to_decimal, SmartOddsExtractor
from ..utils.text import clean_text, normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3
from .mixins import BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin
from .utils.odds_validator import create_odds_data
from ..core.smart_fetcher import BrowserEngine, FetchStrategy, StealthMode
from ..core.exceptions import AdapterHttpError


class SportingLifeAdapter(BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin, BaseAdapterV3):
    """
    Adapter for sportinglife.com, migrated to BaseAdapterV3.
    Hardened with __NEXT_DATA__ JSON parsing for robustness.
    """

    SOURCE_NAME = "SportingLife"
    BASE_URL = "https://www.sportinglife.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(
            primary_engine=BrowserEngine.HTTPX,
            enable_js=False,
            stealth_mode=StealthMode.CAMOUFLAGE,
            block_resources=True,
            timeout=30
        )

    def _get_headers(self) -> dict:
        """Get browser-like headers for SportingLife."""
        return self._get_browser_headers(
            host="www.sportinglife.com",
            referer="https://www.sportinglife.com/racing/racecards",
        )

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all race pages for a given date.
        """
        index_url = f"/racing/racecards/{date}/" if date else "/racing/racecards/"
        resp = await self.make_request("GET", index_url, headers=self._get_headers(), follow_redirects=True)
        if not resp or not resp.text:
            raise AdapterHttpError(self.source_name, 500, index_url)

        self._save_debug_snapshot(resp.text, f"sportinglife_index_{date}")
        parser = HTMLParser(resp.text)
        metadata = self._extract_race_metadata(parser)

        if not metadata:
            return None

        pages = await self._fetch_race_pages_concurrent(metadata, self._get_headers(), semaphore_limit=8)
        return {"pages": pages, "date": date}

    def _extract_race_metadata(self, parser: HTMLParser) -> List[Dict[str, Any]]:
        meta = []
        next_data = parser.css_first("script#__NEXT_DATA__")
        if next_data:
            try:
                data = json.loads(next_data.text())
                for meeting in data.get("props", {}).get("pageProps", {}).get("meetings", []):
                    for i, race in enumerate(meeting.get("races", [])):
                        if url := race.get("racecard_url"):
                            meta.append({"url": url, "race_number": i + 1})
            except:
                pass

        if not meta:
            meetings = parser.css('section[class^="MeetingSummary"]') or parser.css(".meeting-summary")
            for meeting in meetings:
                for i, link in enumerate(meeting.css('a[href*="/racecard/"]')):
                    if url := link.attributes.get("href"):
                        meta.append({"url": url, "race_number": i + 1})
        return meta

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses a list of raw HTML strings into Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        try:
            race_date = datetime.strptime(raw_data["date"], "%Y-%m-%d").date()
        except ValueError:
            return []

        all_races = []
        for item in raw_data["pages"]:
            html_content = item.get("html")
            if not html_content:
                continue
            try:
                parser = HTMLParser(html_content)
                race = self._parse_from_next_data(parser, race_date, item.get("race_number"), html_content)
                if not race:
                    race = self._parse_from_html(parser, race_date, item.get("race_number"), html_content)
                if race:
                    all_races.append(race)
            except Exception as e:
                self.logger.warning("Error parsing SportingLife race", error=str(e))
                continue
        return all_races

    def _parse_from_next_data(self, parser: HTMLParser, race_date, race_number_fallback: Optional[int], html_content: str) -> Optional[Race]:
        """Extract race data from __NEXT_DATA__ JSON tag."""
        next_data = parser.css_first("script#__NEXT_DATA__")
        if not next_data:
            return None

        try:
            data = json.loads(next_data.text())
            race_info = data.get("props", {}).get("pageProps", {}).get("race")
            if not race_info:
                return None

            summary = race_info.get("race_summary") or {}
            track_name = normalize_venue_name(race_info.get("meeting_name") or summary.get("course_name") or "Unknown")
            rt = race_info.get("time") or summary.get("time") or race_info.get("off_time") or race_info.get("start_time")
            if not rt:
                def find_time(obj):
                    if isinstance(obj, str) and re.match(r"^\d{1,2}:\d{2}$", obj):
                        return obj
                    if isinstance(obj, dict):
                        for v in obj.values():
                            if t := find_time(v): return t
                    if isinstance(obj, list):
                        for v in obj:
                            if t := find_time(v): return t
                    return None
                rt = find_time(race_info)

            if not rt:
                return None

            try:
                start_time = datetime.combine(race_date, datetime.strptime(rt, "%H:%M").time())
                start_time = start_time.replace(tzinfo=timezone.utc)
            except:
                return None

            race_num = race_info.get("race_number") or race_number_fallback or 1

            runners = []
            for rd in (race_info.get("runners") or race_info.get("rides") or []):
                name = clean_text(rd.get("horse_name") or rd.get("horse", {}).get("name", ""))
                if not name:
                    continue
                num = rd.get("saddle_cloth_number") or rd.get("cloth_number") or 0
                betting = rd.get("betting") or {}
                wo = parse_odds_to_decimal(
                    betting.get("current_odds") or betting.get("current_price") or
                    rd.get("forecast_price") or rd.get("forecast_odds") or
                    rd.get("betting_forecast_price") or rd.get("odds") or rd.get("bookmakerOdds") or ""
                )

                odds_data = {}
                if wo:
                    odds_data[self.SOURCE_NAME] = OddsData(win=wo, source=self.SOURCE_NAME, last_updated=datetime.now(timezone.utc))

                runners.append(Runner(
                    number=num,
                    name=name,
                    scratched=rd.get("is_non_runner") or rd.get("ride_status") == "NON_RUNNER",
                    odds=odds_data
                ))

            if not runners:
                return None

            # Available bets
            available_bets = []
            html_lower = html_content.lower()
            for kw in ["superfecta", "trifecta", "exacta", "quinella"]:
                if kw in html_lower:
                    available_bets.append(kw.capitalize())

            return Race(
                id=f"sl_{track_name.lower().replace(' ', '')}_{start_time:%Y%m%d}_R{race_num}",
                venue=track_name,
                race_number=race_num,
                start_time=start_time,
                runners=runners,
                distance=summary.get("distance") or race_info.get("distance"),
                source=self.SOURCE_NAME,
                discipline="Thoroughbred",
                metadata={"available_bets": available_bets}
            )
        except:
            return None

    def _parse_from_html(self, parser: HTMLParser, race_date, race_number_fallback: Optional[int], html_content: str) -> Optional[Race]:
        """Fallback HTML parsing logic."""
        h1 = parser.css_first('h1[class*="RacingRacecardHeader__Title"]')
        if not h1:
            return None
        ht = clean_text(h1.text())
        if not ht:
            return None
        parts = ht.split()
        if not parts:
            return None
        try:
            start_time = datetime.combine(race_date, datetime.strptime(parts[0], "%H:%M").time())
            start_time = start_time.replace(tzinfo=timezone.utc)
        except:
            return None

        track_name = normalize_venue_name(" ".join(parts[1:]))
        runners = []
        for row in parser.css('div[class*="RunnerCard"]'):
            try:
                nn = row.css_first('a[href*="/racing/profiles/horse/"]')
                if not nn:
                    continue
                name = clean_text(nn.text()).splitlines()[0].strip()
                num_node = row.css_first('span[class*="SaddleCloth__Number"]')
                number = int("".join(filter(str.isdigit, clean_text(num_node.text())))) if num_node else 0
                on = row.css_first('span[class*="Odds__Price"]')
                wo = parse_odds_to_decimal(clean_text(on.text()) if on else "")

                # Advanced heuristic fallback
                if wo is None:
                    wo = SmartOddsExtractor.extract_from_node(row)

                od = {}
                if wo:
                    od[self.SOURCE_NAME] = OddsData(win=wo, source=self.SOURCE_NAME, last_updated=datetime.now(timezone.utc))
                runners.append(Runner(number=number, name=name, odds=od))
            except:
                continue

        if not runners:
            return None

        dn = parser.css_first('span[class*="RacecardHeader__Distance"]') or parser.css_first(".race-distance")
        distance = clean_text(dn.text()) if dn else None

        # Available bets
        available_bets = []
        html_lower = html_content.lower()
        for kw in ["superfecta", "trifecta", "exacta", "quinella"]:
            if kw in html_lower:
                available_bets.append(kw.capitalize())

        race_num = race_number_fallback or 1

        return Race(
            id=f"sl_{track_name.lower().replace(' ', '')}_{start_time:%Y%m%d}_R{race_num}",
            venue=track_name,
            race_number=race_num,
            start_time=start_time,
            runners=runners,
            distance=distance,
            source=self.SOURCE_NAME,
            metadata={"available_bets": available_bets}
        )
