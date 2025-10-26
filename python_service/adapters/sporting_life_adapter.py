# python_service/adapters/sporting_life_adapter.py

import asyncio
from datetime import datetime
from typing import List
from typing import Optional

import httpx
import structlog
from bs4 import BeautifulSoup
from bs4 import Tag

from ..core.exceptions import AdapterParsingError
from ..models import OddsData
from ..models import Race
from ..models import Runner
from ..utils.odds import parse_odds_to_decimal
from .base import BaseAdapter

log = structlog.get_logger(__name__)


def _clean_text(text: Optional[str]) -> Optional[str]:
    return " ".join(text.strip().split()) if text else None


class SportingLifeAdapter(BaseAdapter):
    """
    Adapter for sportinglife.com.
    This adapter now follows the modern fetch/parse pattern.
    """

    def __init__(self, config):
        super().__init__(source_name="SportingLife", base_url="https://www.sportinglife.com", config=config)

    async def _fetch_data(self, http_client: httpx.AsyncClient, date: str) -> Optional[List[str]]:
        """
        Fetches the raw HTML for all race pages. This involves first getting the
        racecard index, then fetching each individual race page concurrently.
        """
        index_response = await self.make_request(http_client, "GET", "/horse-racing/racecards")
        index_soup = BeautifulSoup(index_response.text, "html.parser")
        links = {a["href"] for a in index_soup.select("a.hr-race-card-meeting__race-link[href]")}

        async def fetch_single_html(url_path: str):
            response = await self.make_request(http_client, "GET", url_path)
            return response.text

        tasks = [fetch_single_html(link) for link in links]
        return await asyncio.gather(*tasks)

    def _parse_races(self, raw_data: List[str]) -> List[Race]:
        """Parses a list of raw HTML strings into Race objects."""
        if not raw_data:
            return []

        all_races = []
        for html in raw_data:
            try:
                soup = BeautifulSoup(html, "html.parser")
                track_name = _clean_text(soup.select_one("a.hr-race-header-course-name__link").get_text())
                race_time_str = _clean_text(soup.select_one("span.hr-race-header-time__time").get_text())
                start_time = datetime.strptime(f"{datetime.now().date()} {race_time_str}", "%Y-%m-%d %H:%M")
                active_link = soup.select_one("a.hr-race-header-navigation-link--active")
                race_number = (
                    soup.select("a.hr-race-header-navigation-link").index(active_link) + 1 if active_link else 1
                )
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
            except (AttributeError, ValueError) as e:
                self.logger.error("Error parsing race from SportingLife", exc_info=e)
                continue  # Continue to the next HTML page
        return all_races

    def _parse_runner(self, row: Tag) -> Optional[Runner]:
        try:
            name = _clean_text(row.select_one("a.hr-racing-runner-horse-name").get_text())
            num_str = _clean_text(row.select_one("span.hr-racing-runner-saddle-cloth-no").get_text())
            number = int("".join(filter(str.isdigit, num_str)))
            odds_str = _clean_text(row.select_one("span.hr-racing-runner-odds").get_text())
            win_odds = parse_odds_to_decimal(odds_str)
            odds_data = (
                {self.source_name: OddsData(win=win_odds, source=self.source_name, last_updated=datetime.now())}
                if win_odds and win_odds < 999
                else {}
            )
            return Runner(number=number, name=name, odds=odds_data)
        except (AttributeError, ValueError):
            log.warning("Failed to parse runner from SportingLife, skipping.")
            return None
