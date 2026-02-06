# python_service/adapters/pointsbet_greyhound_adapter.py

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.smart_fetcher import BrowserEngine, FetchStrategy
from ..models import Race, Runner
from .base_adapter_v3 import BaseAdapterV3
from .utils.odds_validator import create_odds_data


class PointsBetGreyhoundAdapter(BaseAdapterV3):
    """
    Adapter for PointsBet Greyhound API, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "PointsBetGreyhound"
    BASE_URL = "https://api.pointsbet.com/api/v2/sports/greyhound-racing/events/by-date/"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    async def _fetch_data(self, date: str) -> Optional[List[Dict[str, Any]]]:
        """Fetches the raw events data from the PointsBet API."""
        response = await self.make_request("GET", date)
        return response.json() if response else None

    def _parse_races(self, raw_data: Optional[List[Dict[str, Any]]]) -> List[Race]:
        """Parses the raw events data into a list of Race objects."""
        if not raw_data:
            return []

        all_races = []
        for event in raw_data:
            try:
                if race := self._parse_race(event):
                    all_races.append(race)
            except (KeyError, TypeError, ValueError):
                self.logger.error(
                    "Error parsing PointsBet greyhound event",
                    event_id=event.get("eventId"),
                    exc_info=True,
                )
                continue
        return all_races

    def _parse_race(self, event: Dict[str, Any]) -> Optional[Race]:
        """Parses a single event object from the API response."""
        event_id = event.get("eventId")
        venue = event.get("venueName")
        race_number = event.get("raceNumber")
        start_time_str = event.get("startsAt")

        if not all([event_id, venue, race_number, start_time_str]):
            return None

        runners = []
        for runner_data in event.get("runners", []):
            name = runner_data.get("name")
            number = runner_data.get("saddleNumber")
            if not all([name, number]):
                continue

            runners.append(
                Runner(
                    name=name,
                    number=number,
                    scratched=runner_data.get("isScratched", False),
                    odds={},
                )
            )

        if not runners:
            return None

        try:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            start_time = datetime.now()

        return Race(
            id=f"pbg_{event_id}",
            venue=venue,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )
