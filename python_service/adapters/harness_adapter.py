# python_service/adapters/harness_adapter.py
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from zoneinfo import ZoneInfo

from ..models import OddsData
from ..models import Race
from ..models import Runner
from ..utils.odds import parse_odds_to_decimal
from .base_v3 import BaseAdapterV3


class HarnessAdapter(BaseAdapterV3):
    """Adapter for fetching US harness racing data with manual override support."""

    SOURCE_NAME = "USTrotting"
    BASE_URL = "https://data.ustrotting.com/api/racenet/racing/"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config
        )

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        """Fetches all harness races for a given date."""
        response = await self.make_request(self.http_client, "GET", f"card/{date}")

        if not response:
            return None

        card_data = response.json()
        return {"data": card_data, "date": date}

    def _parse_races(self, raw_data: Optional[Dict[str, Any]]) -> List[Race]:
        """Parses the raw card data into a list of Race objects."""
        if (
            not raw_data
            or not raw_data.get("data")
            or not raw_data.get("data", {}).get("meetings")
        ):
            self.logger.warning("No meetings found in harness data response.")
            return []

        all_races = []
        date = raw_data.get("date")
        for meeting in raw_data.get("data", {}).get("meetings", []):
            track_name = meeting.get("track", {}).get("name")
            for race_data in meeting.get("races", []):
                try:
                    if race := self._parse_race(race_data, track_name, date):
                        all_races.append(race)
                except Exception:
                    self.logger.warning(
                        "Failed to parse harness race, skipping.",
                        race_data=race_data,
                        exc_info=True,
                    )
                    continue
        return all_races

    def _parse_race(
        self, race_data: dict, track_name: str, date: str
    ) -> Optional[Race]:
        """Parses a single race from the USTA API into a Race object."""
        race_number = race_data.get("raceNumber")
        post_time_str = race_data.get("postTime")
        if not all([race_number, post_time_str]):
            return None

        start_time = self._parse_post_time(date, post_time_str)

        runners = []
        for runner_data in race_data.get("runners", []):
            if runner_data.get("scratched", False):
                continue

            odds_str = runner_data.get("morningLineOdds", "")
            if "/" not in odds_str and odds_str.isdigit():
                odds_str = f"{odds_str}/1"

            odds = {}
            win_odds = parse_odds_to_decimal(odds_str)
            if win_odds and win_odds < 999:
                odds = {
                    self.SOURCE_NAME: OddsData(
                        win=win_odds,
                        source=self.SOURCE_NAME,
                        last_updated=datetime.now(),
                    )
                }

            runners.append(
                Runner(
                    number=runner_data.get("postPosition", 0),
                    name=runner_data.get("horse", {}).get("name", "Unknown Horse"),
                    odds=odds,
                    scratched=False,
                )
            )

        if not runners:
            return None

        return Race(
            id=f"ust_{track_name.lower().replace(' ', '')}_{date}_{race_number}",
            venue=track_name,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.SOURCE_NAME,
        )

    def _parse_post_time(self, date: str, post_time: str) -> datetime:
        """Parses a time string like '07:00 PM' into a timezone-aware datetime object."""
        dt_str = f"{date} {post_time}"
        naive_dt = datetime.strptime(dt_str, "%Y-%m-%d %I:%M %p")
        # Assume Eastern Time for USTA data, a common standard for US racing.
        eastern = ZoneInfo("America/New_York")
        return naive_dt.replace(tzinfo=eastern)
