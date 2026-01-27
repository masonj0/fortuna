# python_service/adapters/harness_adapter.py
"""Adapter for US harness racing (USTA)."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy
from ..models import Race, Runner
from ..utils.odds import parse_odds_to_decimal
from .base_adapter_v3 import BaseAdapterV3
from .utils.odds_validator import create_odds_data


class HarnessAdapter(BaseAdapterV3):
    """Adapter for fetching US harness racing data."""

    SOURCE_NAME = "USTrotting"
    BASE_URL = "https://data.ustrotting.com/api/racenet/racing/"

    # Eastern timezone is standard for US racing
    TIMEZONE = ZoneInfo("America/New_York")

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config
        )

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        """Fetch harness races for a given date."""
        response = await self.make_request("GET", f"card/{date}")
        if not response:
            return None
        return {"data": response.json(), "date": date}

    def _parse_races(self, raw_data: Optional[Dict[str, Any]]) -> List[Race]:
        """Parse card data into Race objects."""
        if not raw_data:
            return []

        data = raw_data.get("data", {})
        meetings = data.get("meetings", [])

        if not meetings:
            self.logger.warning("No meetings found in harness data response.")
            return []

        races = []
        date = raw_data.get("date")

        for meeting in meetings:
            track_name = meeting.get("track", {}).get("name")
            for race_data in meeting.get("races", []):
                try:
                    if race := self._parse_race(race_data, track_name, date):
                        races.append(race)
                except Exception:
                    self.logger.warning(
                        "Failed to parse harness race",
                        race_data=race_data,
                        exc_info=True,
                    )

        return races

    def _parse_race(
        self, race_data: dict, track_name: str, date: str
    ) -> Optional[Race]:
        """Parse a single race from USTA API."""
        race_number = race_data.get("raceNumber")
        post_time_str = race_data.get("postTime")

        if not all([race_number, post_time_str]):
            return None

        start_time = self._parse_post_time(date, post_time_str)
        runners = self._parse_runners(race_data.get("runners", []))

        if not runners:
            return None

        return Race(
            id=f"ust_{track_name.lower().replace(' ', '')}_{date}_{race_number}",
            venue=track_name,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )

    def _parse_runners(self, runners_data: List[dict]) -> List[Runner]:
        """Parse runner data into Runner objects."""
        runners = []

        for runner_data in runners_data:
            if runner_data.get("scratched", False):
                continue

            odds_str = runner_data.get("morningLineOdds", "")
            # Handle odds like "5" -> "5/1"
            if "/" not in odds_str and odds_str.isdigit():
                odds_str = f"{odds_str}/1"

            win_odds = parse_odds_to_decimal(odds_str)
            odds = {}
            if odds_data := create_odds_data(self.source_name, win_odds):
                odds[self.source_name] = odds_data

            runners.append(
                Runner(
                    number=runner_data.get("postPosition", 0),
                    name=runner_data.get("horse", {}).get("name", "Unknown Horse"),
                    odds=odds,
                    scratched=False,
                )
            )

        return runners

    def _parse_post_time(self, date: str, post_time: str) -> datetime:
        """Parse time string into timezone-aware datetime."""
        dt_str = f"{date} {post_time}"
        naive_dt = datetime.strptime(dt_str, "%Y-%m-%d %I:%M %p")
        return naive_dt.replace(tzinfo=self.TIMEZONE)
