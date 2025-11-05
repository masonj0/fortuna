# python_service/adapters/sporting_life_adapter.py

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
from .base_v3 import BaseAdapterV3


class SportingLifeAdapter(BaseAdapterV3):
    """
    Adapter for sportinglife.com, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "SportingLife"
    BASE_URL = "https://www.sportinglife.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all race pages for a given date.
        Returns a dictionary containing the HTML content and the date.
        """
        index_url = f"/horse-racing/racecards/{date}"
        index_response = await self.make_request(self.http_client, "GET", index_url)
        if not index_response:
            self.logger.warning("Failed to fetch SportingLife index page", url=index_url)
            return None

        index_soup = BeautifulSoup(index_response.text, "html.parser")
        links = {a["href"] for a in index_soup.select("a.hr-race-card-meeting__race-link[href]")}

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
            self.logger.error(
                "Invalid date format provided to SportingLifeAdapter",
                date=raw_data.get("date"),
            )
            return []

        all_races = []
        for html in raw_data["pages"]:
            if not html:
                continue
            try:
                soup = BeautifulSoup(html, "html.parser")

                track_name_node = soup.select_one("a.hr-race-header-course-name__link")
                if not track_name_node:
                    continue
                track_name = clean_text(track_name_node.get_text())

                race_time_node = soup.select_one("span.hr-race-header-time__time")
                if not race_time_node:
                    continue
                race_time_str = clean_text(race_time_node.get_text())

                start_time = datetime.combine(race_date, datetime.strptime(race_time_str, "%H:%M").time())

                active_link = soup.select_one("a.hr-race-header-navigation-link--active")
                race_number = 1
                if active_link:
                    all_links = soup.select("a.hr-race-header-navigation-link")
                    try:
                        race_number = all_links.index(active_link) + 1
                    except ValueError:
                        pass  # Keep default race number if active link not in all links

                runners = [self._parse_runner(row) for row in soup.select("div.hr-racing-runner-card")]

                race = Race(
                    id=f"sl_{track_name.replace(' ', '')}_{start_time.strftime('%Y%m%d')}_R{race_number}",
                    venue=track_name,
                    race_number=race_number,
                    start_time=start_time,
                    runners=[r for r in runners if r],
                    source=self.source_name,
                )
                all_races.append(race)
            except (AttributeError, ValueError):
                self.logger.warning(
                    "Error parsing a race from SportingLife, skipping race.",
                    exc_info=True,
                )
                continue
        return all_races

    def _parse_runner(self, row: Tag) -> Optional[Runner]:
        try:
            name_node = row.select_one("a.hr-racing-runner-horse-name")
            if not name_node:
                return None
            name = clean_text(name_node.get_text())

            num_node = row.select_one("span.hr-racing-runner-saddle-cloth-no")
            if not num_node:
                return None
            num_str = clean_text(num_node.get_text())
            number = int("".join(filter(str.isdigit, num_str)))

            odds_node = row.select_one("span.hr-racing-runner-odds")
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
            self.logger.warning("Failed to parse a runner on SportingLife, skipping runner.")
            return None
