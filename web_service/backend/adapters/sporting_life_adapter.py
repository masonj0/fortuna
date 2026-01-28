# python_service/adapters/sporting_life_adapter.py

import asyncio
import json
import re
from datetime import datetime
from typing import Any, List, Optional

from selectolax.parser import HTMLParser, Node

from ..models import Race, Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text, normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3
from .mixins import BrowserHeadersMixin, DebugMixin
from .utils.odds_validator import create_odds_data
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy, StealthMode


class SportingLifeAdapter(BrowserHeadersMixin, DebugMixin, BaseAdapterV3):
    """
    Adapter for sportinglife.com, migrated to BaseAdapterV3.
    Hardened with __NEXT_DATA__ JSON parsing for robustness.
    """

    SOURCE_NAME = "SportingLife"
    BASE_URL = "https://www.sportinglife.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """
        SportingLife often works with HTTPX as it uses SSR with __NEXT_DATA__.
        If HTTPX fails or returns incomplete data, SmartFetcher will fallback to Playwright.
        """
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
        index_url = "/racing/racecards"
        index_response = await self.make_request(
            "GET",
            index_url,
            headers=self._get_headers(),
            follow_redirects=True,
        )
        if not index_response:
            self.logger.warning("Failed to fetch SportingLife index page", url=index_url)
            return None

        self._save_debug_snapshot(index_response.text, f"sportinglife_index_{date}")

        parser = HTMLParser(index_response.text)

        # Try to extract links from __NEXT_DATA__ first
        links = set()
        next_data_script = parser.css_first("script#__NEXT_DATA__")
        if next_data_script:
            try:
                data = json.loads(next_data_script.text())
                # Navigate to meetings/races in the JSON structure
                meetings = data.get("props", {}).get("pageProps", {}).get("meetings", [])
                for meeting in meetings:
                    for race in meeting.get("races", []):
                        if url := race.get("racecard_url"):
                            links.add(url)
            except (json.JSONDecodeError, KeyError, TypeError):
                self.logger.debug("Failed to extract links from __NEXT_DATA__ on index page")

        # Fallback to HTML selectors if __NEXT_DATA__ failed or was missing
        if not links:
            links = {
                a.attributes["href"]
                for a in parser.css('li[class^="MeetingSummary__LineWrapper"] a[href*="/racecard/"]')
                if a.attributes.get("href")
            }

        if not links:
            links = {
                a.attributes["href"]
                for a in parser.css('.meeting-summary a[href*="/racecard/"]')
                if a.attributes.get("href")
            }

        if not links:
            self.logger.warning("No race links found on SportingLife index page", date=date)
            return None

        self.logger.info(f"Found {len(links)} race links on SportingLife")

        async def fetch_single_html(url_path: str):
            response = await self.make_request("GET", url_path, headers=self._get_headers())
            return response.text if response else ""

        tasks = [fetch_single_html(link) for link in links]
        html_pages = await asyncio.gather(*tasks)
        return {"pages": [p for p in html_pages if p], "date": date}

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses a list of raw HTML strings into Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        try:
            race_date = datetime.strptime(raw_data["date"], "%Y-%m-%d").date()
        except ValueError:
            self.logger.error("Invalid date format", date=raw_data.get("date"))
            return []

        all_races = []
        for html in raw_data["pages"]:
            if not html:
                continue
            try:
                parser = HTMLParser(html)

                # Preferred: Parse from __NEXT_DATA__ JSON
                race = self._parse_from_next_data(parser, race_date)

                # Fallback: Parse from HTML
                if not race:
                    race = self._parse_from_html(parser, race_date)

                if race:
                    all_races.append(race)
            except Exception as e:
                self.logger.warning("Error parsing SportingLife race", error=str(e))
                continue
        return all_races

    def _parse_from_next_data(self, parser: HTMLParser, race_date) -> Optional[Race]:
        """Extract race data from __NEXT_DATA__ JSON tag."""
        script = parser.css_first("script#__NEXT_DATA__")
        if not script:
            return None

        try:
            data = json.loads(script.text())
            race_info = data.get("props", {}).get("pageProps", {}).get("race")
            if not race_info:
                return None

            track_name = normalize_venue_name(race_info.get("meeting_name", "Unknown"))
            race_time_str = race_info.get("time", "")
            if not race_time_str:
                return None

            try:
                start_time = datetime.combine(race_date, datetime.strptime(race_time_str, "%H:%M").time())
            except ValueError:
                return None

            race_number = race_info.get("race_number", 1)

            runners = []
            for runner_data in race_info.get("runners", []):
                name = clean_text(runner_data.get("horse_name", ""))
                number = runner_data.get("saddle_cloth_number", 0)
                if not name:
                    continue

                # Extract odds
                win_odds = None
                betting = runner_data.get("betting", {})
                if betting:
                    # Try to get live price
                    price = betting.get("current_price")
                    if price:
                        win_odds = parse_odds_to_decimal(price)

                # Fallback to 'odds' field if present
                if win_odds is None:
                    win_odds = parse_odds_to_decimal(runner_data.get("odds", ""))

                odds_data = {}
                if odds_val := create_odds_data(self.source_name, win_odds):
                    odds_data[self.source_name] = odds_val

                runners.append(Runner(
                    number=number,
                    name=name,
                    scratched=runner_data.get("is_non_runner", False),
                    odds=odds_data
                ))

            if not runners:
                return None

            return Race(
                id=f"sl_{track_name.replace(' ', '')}_{start_time:%Y%m%d}_R{race_number}",
                venue=track_name,
                race_number=race_number,
                start_time=start_time,
                runners=runners,
                source=self.source_name,
            )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            self.logger.debug("Failed to parse from __NEXT_DATA__", error=str(e))
            return None

    def _parse_from_html(self, parser: HTMLParser, race_date) -> Optional[Race]:
        """Fallback HTML parsing logic."""
        header = parser.css_first('h1[class*="RacingRacecardHeader__Title"]')
        if not header:
            return None

        header_text = clean_text(header.text())
        parts = header_text.split()
        if not parts:
            return None

        race_time_str = parts[0]
        track_name = normalize_venue_name(" ".join(parts[1:]))

        try:
            start_time = datetime.combine(race_date, datetime.strptime(race_time_str, "%H:%M").time())
        except ValueError:
            return None

        race_number = 1
        nav_links = parser.css('a[class*="SubNavigation__Link"]')
        active_link = parser.css_first('a[class*="SubNavigation__Link--active"]')
        if active_link and nav_links:
            try:
                for idx, link in enumerate(nav_links):
                    if link.text().strip() == active_link.text().strip():
                        race_number = idx + 1
                        break
            except Exception:
                pass

        runners = [r for row in parser.css('div[class*="RunnerCard"]') if (r := self._parse_runner_row(row))]

        if not runners:
            return None

        return Race(
            id=f"sl_{track_name.replace(' ', '')}_{start_time:%Y%m%d}_R{race_number}",
            venue=track_name,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )

    def _parse_runner_row(self, row: Node) -> Optional[Runner]:
        """Parse a single runner row from HTML."""
        try:
            name_node = row.css_first('a[href*="/racing/profiles/horse/"]')
            if not name_node:
                return None
            name = clean_text(name_node.text()).splitlines()[0].strip()

            num_node = row.css_first('span[class*="SaddleCloth__Number"]')
            if not num_node:
                return None
            num_str = clean_text(num_node.text())
            number = int("".join(filter(str.isdigit, num_str)))

            odds_node = row.css_first('span[class*="Odds__Price"]')
            odds_str = clean_text(odds_node.text()) if odds_node else ""

            win_odds = parse_odds_to_decimal(odds_str)
            odds_data = {}
            if odds_val := create_odds_data(self.source_name, win_odds):
                odds_data[self.source_name] = odds_val

            return Runner(number=number, name=name, odds=odds_data)
        except (AttributeError, ValueError):
            return None
