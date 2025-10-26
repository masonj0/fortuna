#!/usr/bin/env python3
# This file was generated from the canonical adapter template.
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List

import httpx
import structlog

from ..models import OddsData, Race, Runner
from .base import BaseAdapter

log = structlog.get_logger(__name__)


class TwinSpiresAdapter(BaseAdapter):
    """
    Adapter for twinspires.com.
    This adapter now follows the modern fetch/parse pattern.
    """

    def __init__(self, config):
        super().__init__(source_name="TwinSpires", base_url="https://www.twinspires.com")

    async def _fetch_data(self, http_client: httpx.AsyncClient, date: str) -> Any:
        """Fetches the raw HTML from the TwinSpires race page."""
        url = f"/races/{date}"
        response = await self.make_request(http_client, "GET", url)
        return response.text if response else None

    def _parse_races(self, raw_data: str) -> List[Race]:
        """Parses the raw HTML into a list of Race objects."""
        if not raw_data:
            return []

        from bs4 import BeautifulSoup
        from ..utils.odds import parse_odds_to_decimal

        soup = BeautifulSoup(raw_data, "html.parser")
        race_card = soup.select_one("#race-card")
        if not race_card:
            return []

        race_title_parts = race_card.select_one("h1").text.split(" - ")
        race_number = int(race_title_parts[0].split(" ")[1])
        venue = race_title_parts[1]
        date_str = race_title_parts[2]

        start_time = self._parse_start_time(race_card, date_str)

        runners = []
        for runner_item in race_card.select(".runners-list .runner"):
            if "scratched" in runner_item.get("class", []):
                continue

            number = int(runner_item.select_one(".runner-number").text)
            name = runner_item.select_one(".runner-name").text
            odds_str = runner_item.select_one(".runner-odds").text

            odds_decimal = parse_odds_to_decimal(odds_str)
            odds = {}
            if odds_decimal:
                odds[self.source_name] = OddsData(win=odds_decimal, source=self.source_name, last_updated=datetime.now())

            runners.append(Runner(number=number, name=name, odds=odds, scratched=False))

        race = Race(
            id=f"ts_{venue.replace(' ', '').lower()}_{date_str}_{race_number}",
            venue=venue,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )
        return [race]

    def _parse_start_time(self, soup: "BeautifulSoup", race_date: str) -> datetime:
        from dateutil.parser import parse
        post_time_str = soup.select_one(".post-time").text.replace("Post Time: ", "").strip()
        full_datetime_str = f"{race_date} {post_time_str}"
        return parse(full_datetime_str)
