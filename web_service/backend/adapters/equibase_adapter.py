# python_service/adapters/equibase_adapter.py
import asyncio
from datetime import datetime
from typing import Any
from typing import List
from typing import Optional

from selectolax.parser import HTMLParser
from selectolax.parser import Node

from ..models import Race
from ..models import Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy
from .base_adapter_v3 import BaseAdapterV3
from .mixins import BrowserHeadersMixin, DebugMixin
from .utils.odds_validator import create_odds_data


class EquibaseAdapter(BrowserHeadersMixin, DebugMixin, BaseAdapterV3):
    """
    Adapter for scraping Equibase race entries, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "Equibase"
    BASE_URL = "https://www.equibase.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(
            primary_engine=BrowserEngine.PLAYWRIGHT,
            enable_js=True,
            block_resources=True,
        )

    def _get_headers(self) -> dict:
        return self._get_browser_headers(host="www.equibase.com")

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all race pages for a given date.
        """
        # Try different possible index URLs for Equibase
        index_urls = [
            f"/entries/{date}",
            f"/static/entry/index.html",
            f"/static/entry/{date}/index.html",
        ]

        index_response = None
        for url in index_urls:
            try:
                self.logger.info(f"Trying Equibase index: {url}")
                index_response = await self.make_request("GET", url, headers=self._get_headers())
                if index_response and index_response.text and len(index_response.text) > 1000:
                    break
            except Exception:
                continue

        if not index_response or not index_response.text:
            self.logger.warning("Failed to fetch Equibase index page")
            return None

        self._save_debug_snapshot(index_response.text, f"equibase_index_{date}")

        parser = HTMLParser(index_response.text)
        # More robust race link detection
        race_links = []
        for a in parser.css("a"):
            href = a.attributes.get("href", "")
            if "/static/entry/" in href or "entry-race-level" in a.attributes.get("class", ""):
                 race_links.append(href)

        race_links = list(set(race_links))

        semaphore = asyncio.Semaphore(5)

        async def fetch_single_html(race_url: str):
            async with semaphore:
                try:
                    # Random delay to be less robotic (0.5 to 1.5 seconds)
                    await asyncio.sleep(0.5 + (hash(race_url) % 100) / 100.0)
                    response = await self.make_request("GET", race_url, headers=self._get_headers())
                    return response.text if response else ""
                except Exception as e:
                    self.logger.warning("Failed to fetch race page", url=race_url, error=str(e))
                    return ""

        tasks = [fetch_single_html(link) for link in race_links]
        html_pages = await asyncio.gather(*tasks)
        return {"pages": [p for p in html_pages if p], "date": date}

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses a list of raw HTML strings into Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        date = raw_data["date"]
        all_races = []
        for html in raw_data["pages"]:
            if not html:
                continue
            try:
                parser = HTMLParser(html)

                venue_node = parser.css_first("div.track-information strong")
                if not venue_node:
                    continue
                venue = clean_text(venue_node.text())

                race_number_node = parser.css_first("div.race-information strong")
                if not race_number_node:
                    continue
                race_number_text = race_number_node.text().replace("Race", "").strip()
                if not race_number_text.isdigit():
                    continue
                race_number = int(race_number_text)

                post_time_node = parser.css_first("p.post-time span")
                if not post_time_node:
                    continue
                post_time_str = post_time_node.text().strip()
                start_time = self._parse_post_time(date, post_time_str)

                runners = []
                runner_nodes = parser.css("table.entries-table tbody tr")
                for node in runner_nodes:
                    if runner := self._parse_runner(node):
                        runners.append(runner)

                if not runners:
                    continue

                race = Race(
                    id=f"eqb_{venue.lower().replace(' ', '')}_{date}_{race_number}",
                    venue=venue,
                    race_number=race_number,
                    start_time=start_time,
                    runners=runners,
                    source=self.source_name,
                )
                all_races.append(race)
            except (AttributeError, ValueError):
                self.logger.error("Failed to parse Equibase race page.", exc_info=True)
                continue
        return all_races

    def _parse_runner(self, node: Node) -> Optional[Runner]:
        try:
            number_node = node.css_first("td:nth-child(1)")
            if not number_node or not number_node.text(strip=True).isdigit():
                return None
            number = int(number_node.text(strip=True))

            name_node = node.css_first("td:nth-child(3)")
            if not name_node:
                return None
            name = clean_text(name_node.text())

            odds_node = node.css_first("td:nth-child(10)")
            odds_str = clean_text(odds_node.text()) if odds_node else ""

            scratched = "scratched" in node.attributes.get("class", "").lower()

            odds = {}
            if not scratched:
                win_odds = parse_odds_to_decimal(odds_str)
                if odds_data := create_odds_data(self.source_name, win_odds):
                    odds[self.source_name] = odds_data
            return Runner(number=number, name=name, odds=odds, scratched=scratched)
        except (ValueError, AttributeError, IndexError):
            self.logger.warning("Could not parse Equibase runner, skipping.", exc_info=True)
            return None

    def _parse_post_time(self, date_str: str, time_str: str) -> datetime:
        """Parses a time string like 'Post Time: 12:30 PM ET' into a datetime object."""
        try:
            # Handle formats like "12:30 PM ET" or just "12:30 PM"
            parts = time_str.replace("Post Time:", "").strip().split(" ")
            if len(parts) >= 2:
                time_part = f"{parts[0]} {parts[1]}"
                dt_str = f"{date_str} {time_part}"
                return datetime.strptime(dt_str, "%Y-%m-%d %I:%M %p")
        except Exception:
            self.logger.warning(f"Failed to parse post time: {time_str}")

        # Fallback to a safe default
        return datetime.now()
