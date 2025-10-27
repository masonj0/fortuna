# python_service/adapters/timeform_adapter.py

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


class TimeformAdapter(BaseAdapter):
    """
    Adapter for timeform.com.
    This adapter now follows the modern fetch/parse pattern.
    """

    def __init__(self, config):
        super().__init__(source_name="Timeform", base_url="https://www.timeform.com", config=config)

    async def _fetch_data(self, http_client: httpx.AsyncClient, date: str) -> Optional[List[str]]:
        """
        Fetches the raw HTML for all race pages. This involves first getting the
        racecard index, then fetching each individual race page concurrently.
        """
        index_response = await self.make_request(http_client, "GET", "/horse-racing/racecards")
        index_soup = BeautifulSoup(index_response.text, "html.parser")
        links = {a["href"] for a in index_soup.select("a.rp-racecard-off-link[href]")}

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
                track_name = _clean_text(soup.select_one("h1.rp-raceTimeCourseName_name").get_text())
                race_time_str = _clean_text(soup.select_one("span.rp-raceTimeCourseName_time").get_text())
                start_time = datetime.strptime(f"{datetime.now().date()} {race_time_str}", "%Y-%m-%d %H:%M")
                all_times = [_clean_text(a.get_text()) for a in soup.select("a.rp-racecard-off-link")]
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
            except (AttributeError, ValueError, TypeError) as e:
                self.logger.error("Error parsing race from Timeform", exc_info=True)
                continue
        return all_races

    def _parse_runner(self, row: Tag) -> Optional[Runner]:
        try:
            name = _clean_text(row.select_one("a.rp-horseTable_horse-name").get_text())
            num_str = _clean_text(row.select_one("span.rp-horseTable_horse-number").get_text())
            number_part = "".join(filter(str.isdigit, num_str.strip("()")))
            number = int(number_part)

            odds_data = {}
            if odds_tag := row.select_one("button.rp-bet-placer-btn__odds"):
                odds_str = _clean_text(odds_tag.get_text())
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
            log.warning("Failed to parse runner from Timeform, skipping.")
            return None
