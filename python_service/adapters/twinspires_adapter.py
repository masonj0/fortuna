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
    """Adapter for twinspires.com."""

    def __init__(self, config):
        super().__init__(source_name="TwinSpires", base_url="https://www.twinspires.com")

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> Dict[str, Any]:
        start_time = datetime.now()

        # In a real implementation, this would be a real URL.
        # For now, we're just setting it up to be mocked.
        url = f"{self.base_url}/races/{date}"

        try:
            response = await self.make_request(http_client, "GET", url)
            if not response or response.status_code != 200:
                return self._format_response([], start_time, error_message="Failed to fetch data from TwinSpires")

            races = self._parse_races(response.text)
            return self._format_response(races, start_time)
        except Exception as e:
            log.error("Error fetching races from TwinSpires", error=str(e), exc_info=True)
            return self._format_response([], start_time, error_message=str(e))

    def _parse_start_time(self, soup: "BeautifulSoup", race_date: str) -> datetime:
        from dateutil.parser import parse

        post_time_str = soup.select_one(".post-time").text.replace("Post Time: ", "").strip()

        # Combine the race date with the post time for a full datetime object
        full_datetime_str = f"{race_date} {post_time_str}"
        return parse(full_datetime_str)

    def _parse_races(self, raw_data: str) -> List[Race]:
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

    def _format_response(self, races: List[Race], start_time: datetime, **kwargs) -> Dict[str, Any]:
        return {
            "races": [race.model_dump() for race in races],
            "source_info": {
                "name": self.source_name,
                "status": "SUCCESS" if not kwargs.get("error_message") else "FAILED",
                "races_fetched": len(races),
                "error_message": kwargs.get("error_message"),
                "fetch_duration": (datetime.now() - start_time).total_seconds(),
            },
        }
