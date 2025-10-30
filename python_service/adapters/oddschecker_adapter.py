# python_service/adapters/oddschecker_adapter.py

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from bs4 import BeautifulSoup, Tag

from ..models import OddsData, Race, Runner
from .base_v3 import BaseAdapterV3
from ..utils.odds import parse_odds_to_decimal


class OddscheckerAdapter(BaseAdapterV3):
    """Adapter for scraping horse racing odds from Oddschecker, migrated to BaseAdapterV3."""

    SOURCE_NAME = "Oddschecker"
    BASE_URL = "https://www.oddschecker.com"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config
        )

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all race pages for a given date. This involves a multi-level fetch.
        """
        # Note: Oddschecker doesn't seem to support historical dates well in its main nav,
        # but we build the URL as if it does for future compatibility.
        index_url = f"/horse-racing/{date}"
        index_response = await self.make_request(self.http_client, "GET", index_url)
        if not index_response:
            self.logger.warning("Failed to fetch Oddschecker index page", url=index_url)
            return None

        index_soup = BeautifulSoup(index_response.text, "html.parser")
        # Find all links to individual race pages
        race_links = {a["href"] for a in index_soup.select("a.race-time-link[href]")}

        async def fetch_single_html(url_path: str):
            response = await self.make_request(self.http_client, "GET", url_path)
            return response.text if response else ""

        tasks = [fetch_single_html(link) for link in race_links]
        html_pages = await asyncio.gather(*tasks)
        return {"pages": html_pages, "date": date}

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses a list of raw HTML strings from different races into Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        try:
            race_date = datetime.strptime(raw_data["date"], "%Y-%m-%d").date()
        except ValueError:
            self.logger.error(
                "Invalid date format provided to OddscheckerAdapter",
                date=raw_data.get("date"),
            )
            return []

        all_races = []
        for html in raw_data["pages"]:
            if not html:
                continue
            try:
                soup = BeautifulSoup(html, "html.parser")
                race = self._parse_race_page(soup, race_date)
                if race:
                    all_races.append(race)
            except (AttributeError, IndexError, ValueError):
                self.logger.warning(
                    "Error parsing a race from Oddschecker, skipping race.",
                    exc_info=True,
                )
                continue
        return all_races

    def _parse_race_page(self, soup: BeautifulSoup, race_date) -> Optional[Race]:
        track_name = soup.select_one("h1.meeting-name").get_text(strip=True)
        race_time_str = soup.select_one("span.race-time").get_text(strip=True)

        # Heuristic to find race number from navigation
        active_link = soup.select_one("a.race-time-link.active")
        race_number = 1
        if active_link:
            all_links = soup.select("a.race-time-link")
            race_number = all_links.index(active_link) + 1

        start_time = datetime.combine(
            race_date, datetime.strptime(race_time_str, "%H:%M").time()
        )
        runners = [
            runner
            for row in soup.select("tr.race-card-row")
            if (runner := self._parse_runner_row(row))
        ]

        if not runners:
            return None

        return Race(
            id=f"oc_{track_name.lower().replace(' ', '')}_{start_time.strftime('%Y%m%d')}_r{race_number}",
            venue=track_name,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )

    def _parse_runner_row(self, row: Tag) -> Optional[Runner]:
        try:
            name = row.select_one("span.selection-name").get_text(strip=True)
            odds_str = row.select_one(
                "span.bet-button-odds-desktop, span.best-price"
            ).get_text(strip=True)
            number = int(row.select_one("td.runner-number").get_text(strip=True))

            if not name or not odds_str:
                return None

            win_odds = parse_odds_to_decimal(odds_str)
            odds_dict = {}
            if win_odds and win_odds < 999:
                odds_dict[self.source_name] = OddsData(
                    win=win_odds, source=self.source_name, last_updated=datetime.now()
                )

            return Runner(number=number, name=name, odds=odds_dict)
        except (AttributeError, ValueError):
            self.logger.warning(
                "Failed to parse a runner on Oddschecker, skipping runner."
            )
            return None
