# python_service/adapters/at_the_races_adapter.py
"""Adapter for attheraces.com."""

import asyncio
import re
from datetime import datetime
from typing import Any, List, Optional

from selectolax.parser import HTMLParser, Node

from ..models import Race, Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text, normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3
from .constants import MAX_VALID_ODDS
from .mixins import BrowserHeadersMixin, DebugMixin
from .utils.odds_validator import create_odds_data
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy


class AtTheRacesAdapter(BrowserHeadersMixin, DebugMixin, BaseAdapterV3):
    """
    Adapter for attheraces.com, migrated to BaseAdapterV3.

    Uses simple HTTP requests as the site doesn't require JavaScript.
    """

    SOURCE_NAME = "AtTheRaces"
    BASE_URL = "https://www.attheraces.com"

    # Robust selector strategies with fallbacks
    SELECTORS = {
        "race_links": [
            'a[href^="/racecard/"]',
            'a[href*="/racecard/"]',
        ],
        "details_container": [
            "atr-racecard-race-header .container",
            ".racecard-header .container",
        ],
        "track_name": ["h1 a", "h1"],
        "race_time": ["h1 span", ".race-time"],
        "runners": ["atr-horse-in-racecard", ".horse-in-racecard"],
    }

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config
        )

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """AtTheRaces is a simple HTML site - HTTPX is fastest."""
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX, enable_js=False)

    def _get_headers(self) -> dict:
        """Get headers for ATR requests."""
        return self._get_browser_headers(
            host="www.attheraces.com",
            referer="https://www.attheraces.com/racecards",
        )

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """Fetch race pages for a given date."""
        index_url = f"/racecards/{date}"

        try:
            index_response = await self.make_request(
                "GET", index_url, headers=self._get_headers()
            )
        except Exception as e:
            self.logger.error(
                "Failed to fetch AtTheRaces index page", url=index_url, error=str(e)
            )
            return None

        if not index_response:
            self.logger.warning("No response from AtTheRaces index page", url=index_url)
            return None

        self._save_debug_html(index_response.text, f"atr_index_{date}")

        parser = HTMLParser(index_response.text)
        links = self._find_links_with_fallback(parser)

        if not links:
            self.logger.warning("No race links found on index page", date=date)
            return None

        self.logger.info(f"Found {len(links)} race links for {date}")

        pages = await self._fetch_race_pages(links)
        self.logger.info(f"Successfully fetched {len(pages)}/{len(links)} race pages")

        return {"pages": pages, "date": date}

    def _find_links_with_fallback(self, parser: HTMLParser) -> set:
        """Try multiple selectors to find race links."""
        links = set()
        for selector in self.SELECTORS["race_links"]:
            found = {
                a.attributes["href"]
                for a in parser.css(selector)
                if a.attributes.get("href")
            }
            links.update(found)
        return links

    async def _fetch_race_pages(self, links: set) -> List[tuple]:
        """Fetch all race pages concurrently."""
        async def fetch_single(url_path: str):
            response = await self.make_request(
                "GET", url_path, headers=self._get_headers()
            )
            return (url_path, response.text) if response else (url_path, "")

        tasks = [fetch_single(link) for link in links]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            page for page in results
            if not isinstance(page, Exception) and page and page[1]
        ]

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parse race pages into Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        try:
            race_date = datetime.strptime(raw_data["date"], "%Y-%m-%d").date()
        except ValueError:
            self.logger.error(
                "Invalid date format", date=raw_data.get("date")
            )
            return []

        races = []
        for url_path, html in raw_data["pages"]:
            if not html:
                continue
            try:
                if race := self._parse_single_race(html, url_path, race_date):
                    races.append(race)
            except Exception as e:
                self.logger.warning(
                    "Error parsing race", url=url_path, error=str(e), exc_info=True
                )

        return races

    def _parse_single_race(
        self, html: str, url_path: str, race_date
    ) -> Optional[Race]:
        """Parse a single race from HTML."""
        parser = HTMLParser(html)

        details = self._find_first_match(parser, self.SELECTORS["details_container"])
        if not details:
            return None

        track_node = self._find_first_match(details, self.SELECTORS["track_name"])
        track_name = normalize_venue_name(
            clean_text(track_node.text()) if track_node else ""
        )
        if not track_name:
            return None

        time_node = self._find_first_match(details, self.SELECTORS["race_time"])
        time_str = (
            clean_text(time_node.text()).replace(" ATR", "")
            if time_node else ""
        )
        if not time_str:
            return None

        try:
            start_time = datetime.combine(
                race_date, datetime.strptime(time_str, "%H:%M").time()
            )
        except ValueError:
            self.logger.warning("Invalid time format", time_str=time_str)
            return None

        race_number = self._extract_race_number(url_path)
        runners = self._parse_runners(parser)

        if not runners:
            return None

        return Race(
            id=f"atr_{track_name.replace(' ', '')}_{start_time:%Y%m%d}_R{race_number}",
            venue=track_name,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )

    def _find_first_match(self, parser, selectors: List[str]):
        """Try selectors until one matches."""
        for selector in selectors:
            if node := parser.css_first(selector):
                return node
        return None

    def _extract_race_number(self, url_path: str) -> int:
        """Extract race number from URL path."""
        pattern = r"/racecard/[A-Z]{2}/[A-Za-z-]+/\d{4}-\d{2}-\d{2}/\d{4}/(\d+)"
        if match := re.search(pattern, url_path):
            return int(match.group(1))
        return 1

    def _parse_runners(self, parser: HTMLParser) -> List[Runner]:
        """Parse all runners from the page."""
        runner_nodes = []
        for selector in self.SELECTORS["runners"]:
            if nodes := parser.css(selector):
                runner_nodes = nodes
                break

        return [r for row in runner_nodes if (r := self._parse_runner(row))]

    def _parse_runner(self, row: Node) -> Optional[Runner]:
        """Parse a single runner."""
        try:
            name_node = row.css_first("h3")
            if not name_node:
                return None
            name = clean_text(name_node.text())

            num_node = row.css_first(".horse-in-racecard__saddle-cloth-number")
            if not num_node:
                return None
            num_str = clean_text(num_node.text())
            number = int("".join(filter(str.isdigit, num_str)))

            odds_node = row.css_first(".horse-in-racecard__odds")
            odds_str = clean_text(odds_node.text()) if odds_node else ""
            win_odds = parse_odds_to_decimal(odds_str)

            odds = {}
            if odds_data := create_odds_data(self.source_name, win_odds):
                odds[self.source_name] = odds_data

            return Runner(number=number, name=name, odds=odds)

        except (AttributeError, ValueError) as e:
            self.logger.debug("Failed to parse runner", error=str(e))
            return None
