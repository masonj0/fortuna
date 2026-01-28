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
from .mixins import BrowserHeadersMixin, DebugMixin
from .utils.odds_validator import create_odds_data
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy


class AtTheRacesAdapter(BrowserHeadersMixin, DebugMixin, BaseAdapterV3):
    """
    Adapter for attheraces.com, migrated to BaseAdapterV3.

    Standardized on selectolax for performance.
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
            ".race-header__details--primary",
            "atr-racecard-race-header .container",
            ".racecard-header .container",
        ],
        "track_name": ["h2", "h1 a", "h1"],
        "race_time": ["h2 b", "h1 span", ".race-time"],
        "runners": [".odds-grid-horse", "atr-horse-in-racecard", ".horse-in-racecard"],
    }

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config
        )
        # Limit concurrency to avoid triggering bot protection/timeouts
        self._semaphore = asyncio.Semaphore(5)

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

        self._save_debug_snapshot(index_response.text, f"atr_index_{date}")

        parser = HTMLParser(index_response.text)
        links = self._find_links_with_fallback(parser)

        # Filter out links that are not actual racecards (e.g. /racecards/date)
        # Real racecards usually have a time at the end: /racecard/Venue/Date/Time
        filtered_links = {
            link for link in links
            if re.search(r'/\d{4}$', link) or re.search(r'/\d{1,2}$', link)
        }

        if not filtered_links:
            self.logger.warning("No race links found on index page", date=date)
            return None

        self.logger.info(f"Found {len(filtered_links)} race links for {date}")

        pages = await self._fetch_race_pages(filtered_links)
        self.logger.info(f"Successfully fetched {len(pages)}/{len(filtered_links)} race pages")

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
        """Fetch all race pages concurrently with semaphore limit."""
        async def fetch_single(url_path: str):
            async with self._semaphore:
                try:
                    # Random delay to be less robotic (0.5 to 1.5 seconds)
                    await asyncio.sleep(0.5 + (hash(url_path) % 100) / 100.0)
                    response = await self.make_request(
                        "GET", url_path, headers=self._get_headers()
                    )
                    return (url_path, response.text) if response else (url_path, "")
                except Exception as e:
                    self.logger.warning(f"Failed to fetch {url_path}: {e}")
                    return (url_path, "")

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
                self._save_debug_snapshot(html, f"atr_parse_error_{url_path.split('/')[-1]}", url=url_path)

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
        track_text = clean_text(track_node.text()) if track_node else ""

        # New pattern: "14:32 Dundalk (IRE) 28 Jan 2026"
        time_match = re.search(r'(\d{1,2}:\d{2})', track_text)
        if time_match:
            time_str = time_match.group(1)
            track_name_raw = track_text.replace(time_str, "").strip()
            # Remove date if present (e.g. "28 Jan 2026")
            track_name_raw = re.sub(r'\d{1,2}\s+[A-Za-z]{3}\s+\d{4}', '', track_name_raw).strip()
            track_name = normalize_venue_name(track_name_raw)
        else:
            track_name = normalize_venue_name(track_text)
            time_node = self._find_first_match(details, self.SELECTORS["race_time"])
            time_str = (
                clean_text(time_node.text()).replace(" ATR", "")
                if time_node else ""
            )

        if not track_name or not time_str:
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
        pattern = r"/(\d{1,2})$"
        if match := re.search(pattern, url_path):
            return int(match.group(1))
        return 1

    def _parse_runners(self, parser: HTMLParser) -> List[Runner]:
        """Parse all runners from the page."""
        # We'll map horse IDs to best odds
        odds_map = {}

        # Look in all potential odds grid wrappers
        for wrapper in parser.css(".odds-grid__row-wrapper--entries"):
            for row in wrapper.css(".odds-grid__row--horse"):
                row_id = row.attributes.get("id", "")
                horse_id_match = re.search(r'row-(\d+)', row_id)
                if not horse_id_match:
                    continue
                horse_id = horse_id_match.group(1)

                best_price = row.attributes.get("data-bestprice")
                if best_price:
                    try:
                        odds_map[horse_id] = float(best_price)
                    except ValueError:
                        pass

        runner_nodes = []
        for selector in self.SELECTORS["runners"]:
            if nodes := parser.css(selector):
                runner_nodes = nodes
                break

        runners = []
        for row in runner_nodes:
            runner = self._parse_runner(row, odds_map)
            if runner:
                runners.append(runner)

        return runners

    def _parse_runner(self, row: Node, odds_map: dict) -> Optional[Runner]:
        """Parse a single runner."""
        try:
            # Horse name can be in several places depending on layout
            name_node = row.css_first("h3") or row.css_first('a[href*="/form/horse/"]')
            if not name_node:
                return None
            name = clean_text(name_node.text())

            num_node = row.css_first(".horse-in-racecard__saddle-cloth-number") or row.css_first(".odds-grid-horse__no")
            if not num_node:
                return None
            num_str = clean_text(num_node.text())
            number = int("".join(filter(str.isdigit, num_str)))

            # Try to get horse ID from link to match with odds_map
            horse_id = None
            horse_link = row.css_first('a[href*="/form/horse/"]')
            if horse_link:
                href = horse_link.attributes.get("href", "")
                # Match digits after name and before query params
                horse_id_match = re.search(r'/(\d+)(\?|$)', href)
                if horse_id_match:
                    horse_id = horse_id_match.group(1)

            win_odds = odds_map.get(horse_id) if horse_id else None

            # Fallback to old selector if not in map
            if win_odds is None:
                odds_node = row.css_first(".horse-in-racecard__odds")
                odds_str = clean_text(odds_node.text()) if odds_node else ""
                win_odds = parse_odds_to_decimal(odds_str)

            odds = {}
            if odds_data := create_odds_data(self.source_name, win_odds):
                odds[self.source_name] = odds_data

            return Runner(number=number, name=name, odds=odds)

        except (AttributeError, ValueError):
            return None
