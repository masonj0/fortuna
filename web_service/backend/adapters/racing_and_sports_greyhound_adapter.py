# python_service/adapters/racing_and_sports_greyhound_adapter.py
"""Adapter for Racing and Sports Greyhound API."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.smart_fetcher import BrowserEngine, FetchStrategy
from ..core.exceptions import AdapterConfigError
from ..models import Race, Runner
from .base_adapter_v3 import BaseAdapterV3


class RacingAndSportsGreyhoundAdapter(BaseAdapterV3):
    """Adapter for Racing and Sports Greyhound API, migrated to BaseAdapterV3."""

    SOURCE_NAME = "RacingAndSportsGreyhound"
    BASE_URL = "https://api.racingandsports.com.au/"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config
        )
        if not getattr(config, "RACING_AND_SPORTS_TOKEN", None):
            raise AdapterConfigError(
                self.source_name, "RACING_AND_SPORTS_TOKEN is not configured."
            )
        self.api_token = config.RACING_AND_SPORTS_TOKEN

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        """Fetch greyhound meetings from the Racing and Sports API."""
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }
        params = {"date": date, "jurisdiction": "AUS"}
        response = await self.make_request(
            "GET", "v1/greyhound/meetings", headers=headers, params=params
        )
        return response.json() if response else None

    def _parse_races(self, raw_data: Optional[Dict[str, Any]]) -> List[Race]:
        """Parse meetings data into Race objects."""
        if not raw_data or not isinstance(raw_data.get("meetings"), list):
            self.logger.warning(
                "No 'meetings' in RacingAndSportsGreyhound response or invalid format."
            )
            return []

        races = []
        for meeting in raw_data.get("meetings", []):
            if not isinstance(meeting, dict):
                continue
            for race_summary in meeting.get("races", []):
                if not isinstance(race_summary, dict):
                    continue
                try:
                    if parsed := self._parse_race(meeting, race_summary):
                        races.append(parsed)
                except (KeyError, TypeError, ValueError):
                    self.logger.warning(
                        "Failed to parse greyhound race",
                        venue=meeting.get("venueName"),
                        race_id=race_summary.get("raceId"),
                        exc_info=True,
                    )
        return races

    def _parse_race(
        self, meeting: Dict[str, Any], race: Dict[str, Any]
    ) -> Optional[Race]:
        """Parse a single race from the API response."""
        race_id = race.get("raceId")
        start_time_str = race.get("startTime")
        race_number = race.get("raceNumber")

        if not all([race_id, start_time_str, race_number]):
            return None

        # FIX: Use dogName for greyhounds, not horseName
        runners = [
            Runner(
                number=rd.get("runnerNumber", 0),
                name=rd.get("dogName", rd.get("greyhoundName", "Unknown")),
                scratched=rd.get("isScratched", False),
            )
            for rd in race.get("runners", [])
            if isinstance(rd, dict) and rd.get("runnerNumber")
        ]

        if not runners:
            return None

        try:
            start_time = datetime.fromisoformat(start_time_str)
        except (ValueError, TypeError):
            self.logger.warning(
                "Invalid start time", start_time_str=start_time_str, race_id=race_id
            )
            return None

        return Race(
            id=f"rasg_{race_id}",
            venue=meeting.get("venueName", "Unknown Venue"),
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )
