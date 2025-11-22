# python_service/adapters/equibase_adapter.py
import asyncio
from datetime import datetime
from typing import Any
from typing import List
from typing import Optional

from selectolax.parser import HTMLParser
from selectolax.parser import Node

from ..models import OddsData
from ..models import Race
from ..models import Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text
from .base_adapter_v3 import BaseAdapterV3


class EquibaseAdapter(BaseAdapterV3):
    """
    Adapter for scraping Equibase race entries, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "Equibase"
    BASE_URL = "https://www.equibase.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all race pages for a given date.
        """
        d = datetime.strptime(date, "%Y-%m-%d").date()
        index_url = f"/entries/Entries.cfm?ELEC_DATE={d.month}/{d.day}/{d.year}&STYLE=EQB"
        index_response = await self.make_request(self.http_client, "GET", index_url, headers=self._get_headers())
        if not index_response:
            self.logger.warning("Failed to fetch Equibase index page", url=index_url)
            return None

        parser = HTMLParser(index_response.text)
        track_links = [
            link.attributes["href"]
            for link in parser.css("div.track-information a")
            if "race=" not in link.attributes.get("href", "")
        ]

        async def get_race_links_from_track(track_url: str):
            response = await self.make_request(self.http_client, "GET", track_url, headers=self._get_headers())
            if not response:
                return []
            parser = HTMLParser(response.text)
            return [link.attributes["href"] for link in parser.css("a.program-race-link")]

        tasks = [get_race_links_from_track(link) for link in track_links]
        results = await asyncio.gather(*tasks)
        race_links = [f"{self.base_url}{link}" for sublist in results for link in sublist]

        async def fetch_single_html(race_url: str):
            response = await self.make_request(self.http_client, "GET", race_url, headers=self._get_headers())
            return response.text if response else ""

        tasks = [fetch_single_html(link) for link in race_links]
        html_pages = await asyncio.gather(*tasks)
        return {"pages": html_pages, "date": date}

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
                if win_odds and win_odds < 999:
                    odds = {
                        self.source_name: OddsData(
                            win=win_odds,
                            source=self.source_name,
                            last_updated=datetime.now(),
                        )
                    }
            return Runner(number=number, name=name, odds=odds, scratched=scratched)
        except (ValueError, AttributeError, IndexError):
            self.logger.warning("Could not parse Equibase runner, skipping.", exc_info=True)
            return None

    def _parse_post_time(self, date_str: str, time_str: str) -> datetime:
        """Parses a time string like 'Post Time: 12:30 PM ET' into a datetime object."""
        time_part = time_str.split(" ")[-2] + " " + time_str.split(" ")[-1]
        dt_str = f"{date_str} {time_part}"
        return datetime.strptime(dt_str, "%Y-%m-%d %I:%M %p")

    def _get_headers(self) -> dict:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/107.0.0.0 Safari/537.36"
            )
        }
