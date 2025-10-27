# python_service/adapters/timeform_adapter.py

import asyncio
from datetime import datetime
from typing import Any, List, Optional

from bs4 import BeautifulSoup, Tag

from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text
from .base_v3 import BaseAdapterV3


class TimeformAdapter(BaseAdapterV3):
    """
    Adapter for timeform.com, migrated to BaseAdapterV3.
    """
    SOURCE_NAME = "Timeform"
    BASE_URL = "https://www.timeform.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all race pages for a given date.
        """
        index_url = f"/horse-racing/racecards/{date}"
        index_response = await self.make_request(self.http_client, "GET", index_url)
        if not index_response:
            self.logger.warning("Failed to fetch Timeform index page", url=index_url)
            return None

        index_soup = BeautifulSoup(index_response.text, "html.parser")
        links = {a["href"] for a in index_soup.select("a.rp-racecard-off-link[href]")}

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

        try:
            race_date = datetime.strptime(raw_data["date"], "%Y-%m-%d").date()
        except ValueError:
            self.logger.error("Invalid date format provided to TimeformAdapter", date=raw_data.get("date"))
            return []

        all_races = []
        for html in raw_data["pages"]:
            if not html:
                continue
            try:
                soup = BeautifulSoup(html, "html.parser")
                track_name = clean_text(soup.select_one("h1.rp-raceTimeCourseName_name").get_text())
                race_time_str = clean_text(soup.select_one("span.rp-raceTimeCourseName_time").get_text())
                start_time = datetime.combine(race_date, datetime.strptime(race_time_str, "%H:%M").time())

                all_times = [clean_text(a.get_text()) for a in soup.select("a.rp-racecard-off-link")]
                race_number = all_times.index(race_time_str) + 1 if race_time_str in all_times else 1

                runner_rows = soup.select("div.rp-horseTable_mainRow")
                if not runner_rows:
                    continue

                runners = [self._parse_runner(row) for row in runner_rows]
                race = Race(
                    id=f"tf_{track_name.replace(' ', '')}_{start_time.strftime('%Y%m%d')}_R{race_number}",
                    venue=track_name,
                    race_number=race_number,
                    start_time=start_time,
                    runners=[r for r in runners if r],
                    source=self.source_name,
                )
                all_races.append(race)
            except (AttributeError, ValueError, TypeError):
                self.logger.warning("Error parsing a race from Timeform, skipping race.", exc_info=True)
                continue
        return all_races

    def _parse_runner(self, row: Tag) -> Optional[Runner]:
        try:
            name = clean_text(row.select_one("a.rp-horseTable_horse-name").get_text())
            num_str = clean_text(row.select_one("span.rp-horseTable_horse-number").get_text())
            number_part = "".join(filter(str.isdigit, num_str.strip("()")))
            number = int(number_part)

            odds_data = {}
            if odds_tag := row.select_one("button.rp-bet-placer-btn__odds"):
                odds_str = clean_text(odds_tag.get_text())
                if win_odds := parse_odds_to_decimal(odds_str):
                    if win_odds < 999:
                        odds_data = {
                            self.source_name: OddsData(
                                win=win_odds,
                                source=self.source_name,
                                last_updated=datetime.now(),
                            )
                        }

            return Runner(number=number, name=name, odds=odds_data)
        except (AttributeError, ValueError, TypeError):
            self.logger.warning("Failed to parse a runner from Timeform, skipping runner.")
            return None
