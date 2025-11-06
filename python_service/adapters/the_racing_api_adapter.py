# python_service/adapters/the_racing_api_adapter.py

from datetime import datetime
from decimal import Decimal
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from ..core.exceptions import AdapterConfigError
from ..models import OddsData
from ..models import Race
from ..models import Runner
from .base_v3 import BaseAdapterV3


class TheRacingApiAdapter(BaseAdapterV3):
    """
    Adapter for The Racing API, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "TheRacingAPI"
    BASE_URL = "https://api.theracingapi.com/v1/"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config
        )
        if not hasattr(config, "THE_RACING_API_KEY") or not config.THE_RACING_API_KEY:
            raise AdapterConfigError(
                self.source_name, "THE_RACING_API_KEY is not configured."
            )
        self.api_key = config.THE_RACING_API_KEY

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        """Fetches the raw racecard data from The Racing API."""
        endpoint = f"racecards?date={date}&course=all&region=gb,ire"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = await self.make_request(
            self.http_client, "GET", endpoint, headers=headers
        )
        return response.json() if response else None

    def _parse_races(self, raw_data: Optional[Dict[str, Any]]) -> List[Race]:
        """Parses the raw JSON response into a list of Race objects."""
        if not raw_data or "racecards" not in raw_data:
            self.logger.warning("'racecards' key missing in TheRacingAPI response.")
            return []

        races = []
        for race_data in raw_data.get("racecards", []):
            try:
                race_id = race_data.get("race_id")
                off_time = race_data.get("off_time")
                course = race_data.get("course")
                race_no = race_data.get("race_no")

                if not all([race_id, off_time, course, race_no]):
                    continue

                start_time = datetime.fromisoformat(off_time.replace("Z", "+00:00"))

                race = Race(
                    id=f"tra_{race_id}",
                    venue=course,
                    race_number=race_no,
                    start_time=start_time,
                    runners=self._parse_runners(race_data.get("runners", [])),
                    source=self.source_name,
                    race_name=race_data.get("race_name"),
                    distance=race_data.get("distance_f"),
                )
                races.append(race)
            except Exception:
                self.logger.error(
                    "Error parsing TheRacingAPI race",
                    race_id=race_data.get("race_id"),
                    exc_info=True,
                )
        return races

    def _parse_runners(self, runners_data: List[Dict[str, Any]]) -> List[Runner]:
        runners = []
        for i, runner_data in enumerate(runners_data):
            try:
                horse = runner_data.get("horse")
                if not horse:
                    continue

                odds_data = {}
                odds_list = runner_data.get("odds", [])
                if odds_list:
                    odds_decimal_str = odds_list[0].get("odds_decimal")
                    if odds_decimal_str:
                        win_odds = Decimal(str(odds_decimal_str))
                        odds_data[self.source_name] = OddsData(
                            win=win_odds,
                            source=self.source_name,
                            last_updated=datetime.now(),
                        )

                runners.append(
                    Runner(
                        number=runner_data.get("number", i + 1),
                        name=horse,
                        odds=odds_data,
                        jockey=runner_data.get("jockey"),
                        trainer=runner_data.get("trainer"),
                    )
                )
            except Exception:
                self.logger.error(
                    "Error parsing TheRacingAPI runner",
                    runner_name=runner_data.get("horse"),
                    exc_info=True,
                )
        return runners
