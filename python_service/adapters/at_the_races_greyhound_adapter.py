# python_service/adapters/at_the_races_greyhound_adapter.py

import asyncio
from datetime import datetime
from typing import Any, List, Optional
import uuid

from bs4 import BeautifulSoup, Tag

from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text, normalize_venue_name
from .base_v3 import BaseAdapterV3


class AtTheRacesGreyhoundAdapter(BaseAdapterV3):
    """
    Adapter for the greyhound section of attheraces.com.
    """
    SOURCE_NAME = "AtTheRacesGreyhound"
    BASE_URL = "https://greyhounds.attheraces.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all greyhound race pages for a given date.
        """
        index_url = f"/racecards/{date}"
        index_response = await self.make_request(self.http_client, "GET", index_url)
        if not index_response:
            self.logger.warning("Failed to fetch AtTheRacesGreyhound index page", url=index_url)
            return None

        index_soup = BeautifulSoup(index_response.text, "html.parser")
        # The selector needs to be specific to the racecard links in the main content
        links = {a["href"] for a in index_soup.select("a.racecard[href]")}

        async def fetch_single_html(url_path: str):
            response = await self.make_request(self.http_client, "GET", url_path)
            return response.text if response else ""

        tasks = [fetch_single_html(link) for link in links]
        html_pages = await asyncio.gather(*tasks)
        return {"pages": html_pages, "date": date}


    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses a list of raw HTML strings into Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        all_races = []
        try:
            race_date = datetime.strptime(raw_data["date"], "%Y-%m-%d").date()
        except ValueError:
            self.logger.error("Invalid date format provided to AtTheRacesGreyhoundAdapter", date=raw_data.get("date"))
            return []

        for html in raw_data["pages"]:
            if not html:
                continue
            try:
                soup = BeautifulSoup(html, "html.parser")
                header_text = soup.select_one("h1.heading-racecard-title").get_text(strip=True)

                # Extract venue and time from a string like "Monmore | 18:17"
                parts = [p.strip() for p in header_text.split("|")]
                venue_raw = parts[0]
                time_str = parts[1]

                venue = normalize_venue_name(venue_raw)
                start_time = datetime.combine(race_date, datetime.strptime(time_str, "%H:%M").time())

                # This is a bit brittle, but we can get the race number from the URL
                url_path = soup.find("link", {"rel": "canonical"})["href"]
                race_number = int(url_path.split('/')[-1]) # e.g. /racecard/GB/monmore/20251029/1817/1

                runners = [self._parse_runner(row) for row in soup.select("div.table-default__row--card-runner")]

                race = Race(
                    id=f"atrg_{venue.replace(' ', '')}_{start_time.strftime('%Y%m%d')}_R{race_number}",
                    race_number=race_number,
                    venue=venue,
                    start_time=start_time,
                    runners=[r for r in runners if r],
                    source=self.source_name,
                )
                all_races.append(race)
            except (AttributeError, IndexError, ValueError, TypeError) as e:
                self.logger.warning(f"Error parsing a race from AtTheRacesGreyhound: {e}", exc_info=True)
                continue
        return all_races

    def _parse_runner(self, row: Tag) -> Optional[Runner]:
        try:
            number = int(row.select_one("span.runner-number__no").get_text(strip=True))
            name = row.select_one("span.runner-cloth-name__name").get_text(strip=True)

            odds_button = row.select_one("button.bet-selector__odds")
            win_odds = None
            if odds_button:
                odds_str = odds_button.get_text(strip=True)
                win_odds = parse_odds_to_decimal(odds_str)

            odds_data = (
                {self.source_name: OddsData(win=win_odds, source=self.source_name, last_updated=datetime.now())}
                if win_odds and win_odds < 999
                else {}
            )
            return Runner(number=number, name=name, odds=odds_data)
        except (AttributeError, ValueError, TypeError) as e:
            self.logger.warning(f"Failed to parse a runner on AtTheRacesGreyhound: {e}")
            return None
