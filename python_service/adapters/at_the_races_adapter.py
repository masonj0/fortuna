# python_service/adapters/at_the_races_adapter.py

import asyncio
from datetime import datetime
from typing import List, Optional

import httpx
import structlog
from bs4 import BeautifulSoup, Tag

from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text, normalize_venue_name
from .base import BaseAdapter

log = structlog.get_logger(__name__)


class AtTheRacesAdapter(BaseAdapter):
    def __init__(self, config):
        # The base_url should be the main site for detail pages
        super().__init__(source_name="AtTheRaces", base_url="https://www.attheraces.com", config=config)
        self.mobile_url = "https://m.attheraces.com"

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> List[Race]:
        # Step 1: Fetch the overview from the mobile site to get race links and field sizes
        overview_response = await self.make_request(http_client, "GET", f"{self.mobile_url}/racecards")
        overview_soup = BeautifulSoup(overview_response.text, "html.parser")

        tasks = []
        for meeting in overview_soup.select(".racecard-trends-meetings > h3"):
            race_list = meeting.find_next_sibling("ul")
            for race_link in race_list.select("a[href^='/racecard/']"):
                try:
                    detail_page_url = f"{self.base_url}{race_link['href']}"

                    # Extract field size from the overview page
                    field_size_str = race_link.text.split(" - ")[-1]
                    field_size = int(field_size_str.split(" ")[0])

                    tasks.append(self._fetch_and_parse_race_detail(detail_page_url, field_size, http_client))
                except (ValueError, IndexError):
                    continue

        races = await asyncio.gather(*tasks)
        return [race for race in races if race]

    async def _fetch_and_parse_race_detail(self, url: str, field_size: int, http_client: httpx.AsyncClient) -> Optional[Race]:
        try:
            response = await self.make_request(http_client, "GET", url)
            soup = BeautifulSoup(response.text, "html.parser")

            header = soup.select_one("h1.heading-racecard-title").get_text()
            track_name_raw, race_time = [p.strip() for p in header.split("|")[:2]]
            track_name = normalize_venue_name(track_name_raw)

            # Determine race number by its position in the list
            active_link = soup.select_one("a.race-time-link.active")
            all_races_in_meeting = active_link.find_parent("div", "races").select("a.race-time-link")
            race_number = all_races_in_meeting.index(active_link) + 1

            start_time = datetime.strptime(f"{datetime.now().date()} {race_time}", "%Y-%m-%d %H:%M")

            runners = [self._parse_runner(row) for row in soup.select("div.card-horse")]

            return Race(
                id=f"atr_{track_name.replace(' ', '')}_{start_time.strftime('%Y%m%d')}_R{race_number}",
                venue=track_name,
                race_number=race_number,
                start_time=start_time,
                runners=[r for r in runners if r],
                source=self.source_name,
                field_size=field_size,
            )
        except Exception as e:
            log.error("Error parsing race detail from AtTheRaces", url=url, exc_info=e)
            return None

    def _parse_runner(self, row: Tag) -> Optional[Runner]:
        try:
            name = clean_text(row.select_one("h3.horse-name a").get_text())
            num_str = clean_text(row.select_one("span.horse-number").get_text())
            number = int("".join(filter(str.isdigit, num_str)))
            odds_str = clean_text(row.select_one("button.best-odds").get_text())
            win_odds = parse_odds_to_decimal(odds_str)

            odds = {}
            if win_odds and win_odds < 999:
                odds[self.source_name] = OddsData(win=win_odds, source=self.source_name, last_updated=datetime.now())

            return Runner(number=number, name=name, odds=odds)
        except (AttributeError, ValueError):
            log.warning("Failed to parse a runner on AtTheRaces, skipping runner.")
            return None
