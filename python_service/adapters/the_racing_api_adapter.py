# python_service/adapters/the_racing_api_adapter.py

from datetime import datetime
from typing import Any, Dict, List, Optional

from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy
from ..core.exceptions import AdapterConfigError
from ..models import Race, Runner
from .base_adapter_v3 import BaseAdapterV3
from .utils.odds_validator import create_odds_data


class TheRacingApiAdapter(BaseAdapterV3):
    """
    Adapter for TheRacingAPI.com, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "TheRacingAPI"
    BASE_URL = "https://api.theracingapi.com/v1/"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)
        if not getattr(config, "THE_RACING_API_KEY", None):
            raise AdapterConfigError(self.SOURCE_NAME, "THE_RACING_API_KEY is not configured.")
        self.api_key = config.THE_RACING_API_KEY

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        """Fetches the raw race data from TheRacingAPI."""
        params = {"apiKey": self.api_key, "date": date}
        response = await self.make_request("GET", "racecards/free", params=params)
        return response.json() if response else None

    def _parse_races(self, raw_data: Optional[Dict[str, Any]]) -> List[Race]:
        """Parses the raw JSON data into a list of Race objects."""
        if not raw_data or not isinstance(raw_data.get("racecards"), list):
            self.logger.warning("No 'racecards' in TheRacingAPI response or invalid format.")
            return []

        all_races = []
        for race_summary in raw_data.get("racecards", []):
            try:
                if race := self._parse_single_race(race_summary):
                    all_races.append(race)
            except (KeyError, TypeError, ValueError):
                self.logger.error(
                    "Error parsing TheRacingAPI race",
                    race_id=race_summary.get("race_id"),
                    exc_info=True,
                )
                continue
        return all_races

    def _parse_single_race(self, race_data: Dict[str, Any]) -> Optional[Race]:
        """Parses a single race object from the API response."""
        race_id = race_data.get("race_id")
        venue = race_data.get("course")
        # Handle different potential field names for race number
        race_number = race_data.get("race_number") or race_data.get("race_no")
        start_time_str = race_data.get("off_time")

        if not all([race_id, venue, race_number, start_time_str]):
            return None

        runners = []
        for runner_data in race_data.get("runners", []):
            name = runner_data.get("horse")
            # Handle different potential field names for saddle cloth number
            number = runner_data.get("saddle_cloth") or runner_data.get("number")
            if not all([name, str(number)] if number is not None else [name]):
                continue

            odds = {}
            # TheRacingAPI sometimes provides odds in various formats
            if odds_list := runner_data.get("odds"):
                if isinstance(odds_list, list) and len(odds_list) > 0:
                    odds_val = odds_list[0].get("odds_decimal")
                    if odds_val:
                        if odds_data := create_odds_data(self.source_name, odds_val):
                            odds[self.source_name] = odds_data

            runners.append(
                Runner(
                    name=name,
                    number=number,
                    scratched=runner_data.get("non_runner", False),
                    odds=odds,
                )
            )

        if not runners:
            return None

        # Start time parsing depends on format from API
        try:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            start_time = datetime.now()

        return Race(
            id=f"tra_{race_id}",
            venue=venue,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )
