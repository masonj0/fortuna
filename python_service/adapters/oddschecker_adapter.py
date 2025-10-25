#!/usr/bin/env python3
# ==============================================================================
#  Fortuna Faucet: Oddschecker Adapter (Canonized)
# ==============================================================================
# This adapter was sourced from the 'Live Odds Anthology' and has been modernized
# to conform to the project's current BaseAdapter framework.
# ==============================================================================

import asyncio
from datetime import datetime
from decimal import Decimal
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
from .base import BaseAdapter
from .utils import parse_odds

log = structlog.get_logger(__name__)


class OddscheckerAdapter(BaseAdapter):
    """Adapter for scraping live horse racing odds from Oddschecker."""

    def __init__(self, config):
        super().__init__(source_name="Oddschecker", base_url="https://www.oddschecker.com", config=config)

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> List[Race]:
        meeting_links = await self._get_all_meeting_links(http_client)
        if not meeting_links:
            return []

        tasks = [self._fetch_single_meeting(link, http_client) for link in meeting_links]
        races_from_all_meetings = await asyncio.gather(*tasks)

        return [race for sublist in races_from_all_meetings for race in sublist if race]

    async def _get_all_meeting_links(self, http_client: httpx.AsyncClient) -> List[str]:
        response = await self.make_request(http_client, "GET", "/horse-racing")
        soup = BeautifulSoup(response.text, "html.parser")
        links = {self.base_url + a["href"] for a in soup.select("a.meeting-title[href]")}
        return sorted(list(links))

    async def _fetch_single_meeting(self, url: str, client: httpx.AsyncClient) -> List[Optional[Race]]:
        response = await self.make_request(client, "GET", url.replace(self.base_url, ""))
        soup = BeautifulSoup(response.text, "html.parser")
        race_links = {self.base_url + a["href"] for a in soup.select("a.race-time-link[href]")}
        tasks = [self._fetch_and_parse_race_card(link, client) for link in race_links]
        return await asyncio.gather(*tasks)

    async def _fetch_and_parse_race_card(self, url: str, client: httpx.AsyncClient) -> Optional[Race]:
        try:
            response = await self.make_request(client, "GET", url.replace(self.base_url, ""))
            soup = BeautifulSoup(response.text, "html.parser")
            return self._parse_race_page(soup, url)
        except (AttributeError, IndexError, ValueError) as e:
            log.error("Oddschecker failed to parse race card", url=url, error=e)
            raise AdapterParsingError(self.source_name, f"Failed to parse race card at {url}") from e

    def _parse_race_page(self, soup: BeautifulSoup, url: str) -> Optional[Race]:
        track_name = soup.select_one("h1.meeting-name").get_text(strip=True)
        race_time_str = soup.select_one("span.race-time").get_text(strip=True)
        race_number = int(url.split("-")[-1]) if "race-" in url else 0

        runners = [runner for row in soup.select("tr.race-card-row") if (runner := self._parse_runner_row(row))]
        if not runners:
            return None

        today_str = datetime.now().strftime("%Y-%m-%d")
        start_time = datetime.strptime(f"{today_str} {race_time_str}", "%Y-%m-%d %H:%M")

        return Race(
            id=f"oc_{track_name.lower().replace(' ', '')}_{start_time.strftime('%Y%m%d')}_r{race_number}",
            venue=track_name,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name
        )

    def _parse_runner_row(self, row: Tag) -> Optional[Runner]:
        name = row.select_one("span.selection-name").get_text(strip=True)
        odds_str = row.select_one("span.bet-button-odds-desktop, span.best-price").get_text(strip=True)
        number = int(row.select_one("td.runner-number").get_text(strip=True))

        if not name or not odds_str:
            return None

        odds_val = parse_odds(odds_str)
        odds_dict = {}
        if odds_val:
            odds_dict[self.source_name] = OddsData(
                win=Decimal(str(odds_val)), source=self.source_name, last_updated=datetime.now()
            )

        return Runner(number=number, name=name, odds=odds_dict)
