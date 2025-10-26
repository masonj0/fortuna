# python_service/adapters/at_the_races_adapter.py

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
from ..utils.text import clean_text
from ..utils.text import normalize_venue_name
from .base import BaseAdapter

log = structlog.get_logger(__name__)


class AtTheRacesAdapter(BaseAdapter):
    """
    Adapter for attheraces.com.
    This adapter now follows the modern fetch/parse pattern.
    """

    def __init__(self, config):
        super().__init__(source_name="AtTheRaces", base_url="https://www.attheraces.com", config=config)

    async def _fetch_data(self, http_client: httpx.AsyncClient, date: str) -> Optional[List[str]]:
        """
        Fetches the raw HTML for all race pages. This involves first getting the
        racecard index, then fetching each individual race page concurrently.
        """
        index_response = await self.make_request(http_client, "GET", "/racecards")
        index_soup = BeautifulSoup(index_response.text, "html.parser")
        links = {a["href"] for a in index_soup.select("a.race-time-link[href]")}

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
                header = soup.select_one("h1.heading-racecard-title").get_text()
                track_name_raw, race_time = [p.strip() for p in header.split("|")[:2]]
                track_name = normalize_venue_name(track_name_raw)
                active_link = soup.select_one("a.race-time-link.active")
                race_number = (
                    active_link.find_parent("div", "races").select("a.race-time-link").index(active_link) + 1
                )
                start_time = datetime.strptime(f"{datetime.now().date()} {race_time}", "%Y-%m-%d %H:%M")
                runners = [self._parse_runner(row) for row in soup.select("div.card-horse")]
                race = Race(
                    id=f"atr_{track_name.replace(' ', '')}_{start_time.strftime('%Y%m%d')}_R{race_number}",
                    venue=track_name,
                    race_number=race_number,
                    start_time=start_time,
                    runners=[r for r in runners if r],
                    source=self.source_name,
                )
                all_races.append(race)
            except (AttributeError, IndexError, ValueError) as e:
                self.logger.error("Error parsing race from AtTheRaces", exc_info=True)
                continue
        return all_races

    def _parse_runner(self, row: Tag) -> Optional[Runner]:
        try:
            name = clean_text(row.select_one("h3.horse-name a").get_text())
            num_str = clean_text(row.select_one("span.horse-number").get_text())
            number = int("".join(filter(str.isdigit, num_str)))
            odds_str = clean_text(row.select_one("button.best-odds").get_text())
            win_odds = parse_odds_to_decimal(odds_str)
            odds_data = (
                {self.source_name: OddsData(win=win_odds, source=self.source_name, last_updated=datetime.now())}
                if win_odds and win_odds < 999
                else {}
            )
            return Runner(number=number, name=name, odds=odds_data)
        except (AttributeError, ValueError):
            # If a runner can't be parsed, log it but don't fail the whole race
            log.warning("Failed to parse a runner on AtTheRaces, skipping runner.")
            return None
