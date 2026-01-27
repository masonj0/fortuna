# python_service/adapters/at_the_races_adapter.py
# FIXED VERSION - Added missing 're' import

import asyncio
import re  # <--- CRITICAL FIX: This was missing! Line 98 uses re.search()
from datetime import datetime
from typing import Any
from typing import List
from typing import Optional

from selectolax.parser import HTMLParser, Node

from ..models import OddsData
from ..models import Race
from ..models import Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text
from ..utils.text import normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy


class AtTheRacesAdapter(BaseAdapterV3):
    """
    Adapter for attheraces.com, migrated to BaseAdapterV3.

    IMPROVEMENTS:
    - Added missing 're' import (was causing runtime errors)
    - Enhanced error handling with debug snapshots
    - Better selector fallback logic
    - Improved logging
    """

    SOURCE_NAME = "AtTheRaces"
    BASE_URL = "https://www.attheraces.com"

    # Robust selector strategies with fallbacks
    SELECTORS = {
        'race_links': [
            'a[href^="/racecard/"]',
            'a[href*="/racecard/"]',  # More lenient fallback
        ],
        'details_container': [
            'atr-racecard-race-header .container',
            '.racecard-header .container',  # Fallback
        ],
        'track_name': [
            'h1 a',
            'h1',  # Fallback
        ],
        'race_time': [
            'h1 span',
            '.race-time',  # Fallback
        ],
        'runners': [
            'atr-horse-in-racecard',
            '.horse-in-racecard',  # Fallback
        ]
    }

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """
        AtTheRaces is a simple HTML site and does not require JavaScript.
        Using HTTPX is much faster and more efficient.
        """
        return FetchStrategy(
            primary_engine=BrowserEngine.HTTPX,
            enable_js=False,
        )

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all race pages for a given date.
        Returns a dictionary containing a list of (URL, HTML content) tuples and the date.
        """
        index_url = f"/racecards/{date}"

        try:
            index_response = await self.make_request("GET", index_url, headers=self._get_headers())
        except Exception as e:
            self.logger.error("Failed to fetch AtTheRaces index page", url=index_url, error=str(e))
            return None

        if not index_response:
            self.logger.warning("No response from AtTheRaces index page", url=index_url)
            return None

        parser = HTMLParser(index_response.text)

        # Try multiple selectors to find race links
        links = set()
        for selector in self.SELECTORS['race_links']:
            found_links = {a.attributes["href"] for a in parser.css(selector) if a.attributes.get("href")}
            links.update(found_links)

        if not links:
            self.logger.warning("No race links found on index page", date=date)
            return None

        self.logger.info(f"Found {len(links)} race links for {date}")

        async def fetch_single_html(url_path: str):
            response = await self.make_request("GET", url_path, headers=self._get_headers())
            return (url_path, response.text) if response else (url_path, "")

        tasks = [fetch_single_html(link) for link in links]
        html_pages_with_urls = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and empty responses
        valid_pages = [
            page for page in html_pages_with_urls
            if not isinstance(page, Exception) and page and page[1]
        ]

        self.logger.info(f"Successfully fetched {len(valid_pages)}/{len(links)} race pages")

        return {"pages": valid_pages, "date": date}

    def _get_headers(self) -> dict:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Host": "www.attheraces.com",
            "Pragma": "no-cache",
            "sec-ch-ua": '"Not/A)Brand";v="99", "Google Chrome";v="115", "Chromium";v="115"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Referer": "https://www.attheraces.com/racecards",
        }

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses a list of (URL, raw HTML string) tuples into Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        try:
            race_date = datetime.strptime(raw_data["date"], "%Y-%m-%d").date()
        except ValueError:
            self.logger.error(
                "Invalid date format provided to AtTheRacesAdapter",
                date=raw_data.get("date"),
            )
            return []

        all_races = []
        for url_path, html in raw_data["pages"]:
            if not html:
                continue

            try:
                race = self._parse_single_race(html, url_path, race_date)
                if race:
                    all_races.append(race)
            except Exception as e:
                self.logger.warning(
                    "Error parsing race from AtTheRaces",
                    url=url_path,
                    error=str(e),
                    exc_info=True,
                )
                continue

        return all_races

    def _parse_single_race(self, html: str, url_path: str, race_date) -> Optional[Race]:
        """Parse a single race from HTML"""
        parser = HTMLParser(html)

        # Find details container with fallback
        details_container = None
        for selector in self.SELECTORS['details_container']:
            details_container = parser.css_first(selector)
            if details_container:
                break

        if not details_container:
            self.logger.debug("No details container found", url=url_path)
            return None

        # Extract track name
        track_name_node = None
        for selector in self.SELECTORS['track_name']:
            track_name_node = details_container.css_first(selector)
            if track_name_node:
                break

        track_name_raw = clean_text(track_name_node.text()) if track_name_node else ""
        track_name = normalize_venue_name(track_name_raw)

        if not track_name:
            self.logger.debug("No track name found", url=url_path)
            return None

        # Extract race time
        race_time_node = None
        for selector in self.SELECTORS['race_time']:
            race_time_node = details_container.css_first(selector)
            if race_time_node:
                break

        race_time_str = (
            clean_text(race_time_node.text()).replace(" ATR", "")
            if race_time_node else ""
        )

        if not race_time_str:
            self.logger.debug("No race time found", url=url_path)
            return None

        try:
            start_time = datetime.combine(
                race_date,
                datetime.strptime(race_time_str, "%H:%M").time()
            )
        except ValueError as e:
            self.logger.warning("Invalid time format", time_str=race_time_str, error=str(e))
            return None

        # Extract race number from URL
        # Pattern: /racecard/GB/Cheltenham/2024-01-26/1430/1
        race_number_match = re.search(
            r'/racecard/[A-Z]{2}/[A-Za-z-]+/\d{4}-\d{2}-\d{2}/\d{4}/(\d+)',
            url_path
        )
        race_number = int(race_number_match.group(1)) if race_number_match else 1

        # Parse runners with fallback selectors
        runner_nodes = []
        for selector in self.SELECTORS['runners']:
            runner_nodes = parser.css(selector)
            if runner_nodes:
                break

        runners = [self._parse_runner(row) for row in runner_nodes]
        runners = [r for r in runners if r]  # Filter None values

        if not runners:
            self.logger.debug("No runners found", url=url_path)
            return None

        race = Race(
            id=f"atr_{track_name.replace(' ', '')}_{start_time.strftime('%Y%m%d')}_R{race_number}",
            venue=track_name,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )

        return race

    def _parse_runner(self, row: Node) -> Optional[Runner]:
        """Parse a single runner from HTML"""
        try:
            # Horse name
            name_node = row.css_first("h3")
            if not name_node:
                return None
            name = clean_text(name_node.text())

            # Saddle cloth number
            num_node = row.css_first(".horse-in-racecard__saddle-cloth-number")
            if not num_node:
                return None
            num_str = clean_text(num_node.text())
            number = int("".join(filter(str.isdigit, num_str)))

            # Odds
            odds_node = row.css_first(".horse-in-racecard__odds")
            odds_str = clean_text(odds_node.text()) if odds_node else ""

            win_odds = parse_odds_to_decimal(odds_str)
            odds_data = (
                {
                    self.source_name: OddsData(
                        win=win_odds,
                        source=self.source_name,
                        last_updated=datetime.now(),
                    )
                }
                if win_odds and win_odds < 999
                else {}
            )

            return Runner(number=number, name=name, odds=odds_data)

        except (AttributeError, ValueError) as e:
            self.logger.debug("Failed to parse runner", error=str(e))
            return None
