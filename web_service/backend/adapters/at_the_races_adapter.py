# python_service/adapters/at_the_races_adapter.py

import asyncio
from datetime import datetime
from typing import Any
from typing import List
from typing import Optional

from bs4 import BeautifulSoup
from bs4 import Tag

from ..models import OddsData
from ..models import Race
from ..models import Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text
from ..utils.text import normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3


class AtTheRacesAdapter(BaseAdapterV3):
    """
    Adapter for attheraces.com, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "AtTheRaces"
    BASE_URL = "https://www.attheraces.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all race pages for a given date.
        Returns a dictionary containing a list of (URL, HTML content) tuples and the date.
        """
        index_url = f"/racecards/{date}"
        index_response = await self.make_request(
            self.http_client, "GET", index_url, headers=self._get_headers()
        )
        if not index_response:
            self.logger.warning("Failed to fetch AtTheRaces index page", url=index_url)
            return None

        index_soup = BeautifulSoup(index_response.text, "html.parser")
        links = {a["href"] for a in index_soup.select("a.race-card-header__link")}

        async def fetch_single_html(url_path: str):
            response = await self.make_request(
                self.http_client, "GET", url_path, headers=self._get_headers()
            )
            return (url_path, response.text) if response else (url_path, "")

        tasks = [fetch_single_html(link) for link in links]
        html_pages_with_urls = await asyncio.gather(*tasks)
        return {"pages": html_pages_with_urls, "date": date}

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
                soup = BeautifulSoup(html, "html.parser")
                details_container = soup.select_one("atr-racecard-race-header .container")
                if not details_container:
                    continue

                track_name_node = details_container.select_one("h1 a")
                track_name_raw = clean_text(track_name_node.get_text()) if track_name_node else ""
                track_name = normalize_venue_name(track_name_raw)

                race_time_node = details_container.select_one("h1 span")
                race_time_str = (
                    clean_text(race_time_node.get_text()).replace(" ATR", "") if race_time_node else ""
                )

                start_time = datetime.combine(
                    race_date, datetime.strptime(race_time_str, "%H:%M").time()
                )

                race_number = 1
                try:
                    parts = url_path.split("/")
                    race_number = int([part for part in parts if part.isdigit()][-1])
                except (ValueError, IndexError):
                    self.logger.warning("Could not parse race number from URL", url=url_path)

                runners = [self._parse_runner(row) for row in soup.select("atr-horse-in-racecard")]

                race = Race(
                    id=f"atr_{track_name.replace(' ', '')}_{start_time.strftime('%Y%m%d')}_R{race_number}",
                    venue=track_name,
                    race_number=race_number,
                    start_time=start_time,
                    runners=[r for r in runners if r],
                    source=self.source_name,
                )
                all_races.append(race)
            except (AttributeError, ValueError):
                self.logger.warning(
                    "Error parsing a race from AtTheRaces, skipping race.",
                    exc_info=True,
                )
                continue
        return all_races

    def _parse_runner(self, row: Tag) -> Optional[Runner]:
        try:
            name_node = row.select_one("h3")
            if not name_node:
                return None
            name = clean_text(name_node.get_text())

            num_node = row.select_one(".horse-in-racecard__saddle-cloth-number")
            if not num_node:
                return None
            num_str = clean_text(num_node.get_text())
            number = int("".join(filter(str.isdigit, num_str)))

            odds_node = row.select_one(".horse-in-racecard__odds")
            odds_str = clean_text(odds_node.get_text()) if odds_node else ""

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
        except (AttributeError, ValueError):
            self.logger.warning("Failed to parse a runner on AtTheRaces, skipping runner.")
            return None
