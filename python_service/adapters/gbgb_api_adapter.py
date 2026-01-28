# python_service/adapters/gbgb_api_adapter.py

from datetime import datetime
from typing import Any, Dict, List, Optional

from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy
from ..models import Race, Runner
from ..utils.odds import parse_odds_to_decimal
from .base_adapter_v3 import BaseAdapterV3
from .utils.odds_validator import create_odds_data


class GbgbApiAdapter(BaseAdapterV3):
    """
    Adapter for the Greyhound Board of Great Britain API, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "GBGB"
    BASE_URL = "https://api.gbgb.org.uk/api/"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    async def _fetch_data(self, date: str) -> Optional[List[Dict[str, Any]]]:
        """Fetches the raw meeting data from the GBGB API."""
        endpoint = f"results/meeting/{date}"
        response = await self.make_request("GET", endpoint)
        return response.json() if response else None

    def _parse_races(self, meetings_data: Optional[List[Dict[str, Any]]]) -> List[Race]:
        """Parses the raw meeting data into a list of Race objects."""
        if not meetings_data:
            return []

        all_races = []
        for meeting in meetings_data:
            track_name = meeting.get("trackName")
            for race_data in meeting.get("races", []):
                try:
                    if race := self._parse_race(race_data, track_name):
                        all_races.append(race)
                except (KeyError, TypeError):
                    self.logger.error(
                        "Error parsing GBGB race",
                        race_id=race_data.get("raceId"),
                        exc_info=True,
                    )
                    continue
        return all_races

    def _parse_race(self, race_data: Dict[str, Any], track_name: str) -> Optional[Race]:
        """Parses a single race object from the API response."""
        race_id = race_data.get("raceId")
        race_number = race_data.get("raceNumber")
        race_time = race_data.get("raceTime")

        if not all([race_id, race_number, race_time]):
            return None

        return Race(
            id=f"gbgb_{race_id}",
            venue=track_name,
            race_number=race_number,
            start_time=datetime.fromisoformat(race_time.replace("Z", "+00:00")),
            runners=self._parse_runners(race_data.get("traps", [])),
            source=self.source_name,
            race_name=race_data.get("raceTitle"),
            distance=f"{race_data.get('raceDistance')}m",
        )

    def _parse_runners(self, runners_data: List[Dict[str, Any]]) -> List[Runner]:
        """Parses a list of runner dictionaries into Runner objects."""
        runners = []
        for runner_data in runners_data:
            try:
                trap_number = runner_data.get("trapNumber")
                dog_name = runner_data.get("dogName")
                if not all([trap_number, dog_name]):
                    continue

                odds_data = {}
                sp = runner_data.get("sp")
                if sp:
                    win_odds = parse_odds_to_decimal(sp)
                    if odds_data_val := create_odds_data(self.source_name, win_odds):
                        odds_data[self.source_name] = odds_data_val

                runners.append(
                    Runner(
                        number=trap_number,
                        name=dog_name,
                        odds=odds_data,
                    )
                )
            except (KeyError, TypeError):
                self.logger.warning(
                    "Error parsing GBGB runner, skipping.",
                    runner_name=runner_data.get("dogName"),
                )
                continue
        return runners
