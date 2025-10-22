# python_service/adapters/equibase_adapter.py
from datetime import datetime
from typing import List, Optional
import asyncio

from selectolax.parser import HTMLParser

from ..core.exceptions import AdapterParsingError
from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text
from .base import BaseAdapter


class EquibaseAdapter(BaseAdapter):
    """A production-ready adapter for scraping Equibase race entries."""

    def __init__(self, config=None):
        super().__init__(source_name="Equibase", base_url="https://www.equibase.com", config=config)

    async def fetch_races(self, date_str: str, http_client) -> List[Race]:
        """
        Fetches all US & Canadian races for a given date from equibase.com.
        """
        entry_urls = await self._get_entry_urls(date_str, http_client)

        tasks = [self._fetch_races_from_entry_page(url, date_str, http_client) for url in entry_urls]
        results = await asyncio.gather(*tasks)

        # Flatten the list of lists into a single list of races
        return [race for sublist in results for race in sublist]

    async def _get_entry_urls(self, date_str: str, http_client) -> list[str]:
        """Gets all individual track entry page URLs for a given date."""
        d = datetime.strptime(date_str, "%Y-%m-%d").date()
        url = f"/entries/Entries.cfm?ELEC_DATE={d.month}/{d.day}/{d.year}&STYLE=EQB"
        response = await self.make_request(http_client, "GET", url, headers=self._get_headers())
        parser = HTMLParser(response.text)
        links = parser.css("div.track-information a")
        return [
            f"{self.base_url}{link.attributes['href']}"
            for link in links
            if "race=" not in link.attributes.get("href", "")
        ]

    async def _fetch_races_from_entry_page(self, url: str, date_str: str, http_client) -> List[Race]:
        """Fetches all race data from a single track's entry page."""
        response = await self.make_request(http_client, "GET", url, headers=self._get_headers())
        parser = HTMLParser(response.text)
        race_links = parser.css("a.program-race-link")

        tasks = [self._parse_race_page(f"{self.base_url}{link.attributes['href']}", date_str, http_client) for link in race_links]
        return [race for race in await asyncio.gather(*tasks) if race]


    async def _parse_race_page(self, url: str, date_str: str, http_client) -> Optional[Race]:
        """Parses a single race card page."""
        try:
            response = await self.make_request(http_client, "GET", url, headers=self._get_headers())
            parser = HTMLParser(response.text)

            venue = clean_text(parser.css_first("div.track-information strong").text())
            race_number = int(parser.css_first("div.race-information strong").text().replace("Race", "").strip())
            post_time_str = parser.css_first("p.post-time span").text().strip()
            start_time = self._parse_post_time(date_str, post_time_str)

            runners = []
            runner_nodes = parser.css("table.entries-table tbody tr")
            for node in runner_nodes:
                try:
                    number = int(node.css_first("td:nth-child(1)").text(strip=True))
                    name = clean_text(node.css_first("td:nth-child(3)").text())
                    odds_str = clean_text(node.css_first("td:nth-child(10)").text())
                    scratched = "scratched" in node.attributes.get("class", "").lower()

                    odds = {}
                    if not scratched:
                        win_odds = parse_odds_to_decimal(odds_str)
                        if win_odds and win_odds < 999:
                            odds = {
                                self.source_name: OddsData(
                                    win=win_odds, source=self.source_name, last_updated=datetime.now()
                                )
                            }

                    runners.append(Runner(number=number, name=name, odds=odds, scratched=scratched))
                except (ValueError, AttributeError):
                    # Log and skip the problematic runner
                    self.logger.warning("Could not parse runner, skipping.", url=url)
                    continue

            return Race(
                id=f"eqb_{venue.lower().replace(' ', '')}_{date_str}_{race_number}",
                venue=venue,
                race_number=race_number,
                start_time=start_time,
                runners=runners,
                source=self.source_name,
            )
        except (AttributeError, ValueError) as e:
            raise AdapterParsingError(self.source_name, f"Failed to parse race page at {url}") from e

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
