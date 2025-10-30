# python_service/adapters/racing_and_sports_greyhound_adapter.py

from datetime import datetime
from typing import Any, Dict, List, Optional

from ..core.exceptions import AdapterConfigError
from ..models import Race, Runner
from .base_v3 import BaseAdapterV3


class RacingAndSportsGreyhoundAdapter(BaseAdapterV3):
    """Adapter for Racing and Sports Greyhound API, migrated to BaseAdapterV3."""

    SOURCE_NAME = "RacingAndSportsGreyhound"
    BASE_URL = "https://api.racingandsports.com.au/"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config
        )
        if (
            not hasattr(config, "RACING_AND_SPORTS_TOKEN")
            or not config.RACING_AND_SPORTS_TOKEN
        ):
            raise AdapterConfigError(
                self.source_name, "RACING_AND_SPORTS_TOKEN is not configured."
            )
        self.api_token = config.RACING_AND_SPORTS_TOKEN

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        """Fetches the raw greyhound meetings data from the Racing and Sports API."""
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }
        params = {"date": date, "jurisdiction": "AUS"}
        response = await self.make_request(
            self.http_client,
            "GET",
            "v1/greyhound/meetings",
            headers=headers,
            params=params,
        )
        return response.json() if response else None

    def _parse_races(self, raw_data: Dict[str, Any]) -> List[Race]:
        """Parses the raw meetings data into a list of Race objects."""
        all_races = []
        if not raw_data or not isinstance(raw_data.get("meetings"), list):
            self.logger.warning(
                "No 'meetings' in RacingAndSportsGreyhound response or invalid format."
            )
            return all_races

        for meeting in raw_data["meetings"]:
            if not isinstance(meeting, dict):
                continue
            for race_summary in meeting.get("races", []):
                if not isinstance(race_summary, dict):
                    continue
                try:
                    if parsed_race := self._parse_ras_race(meeting, race_summary):
                        all_races.append(parsed_race)
                except (KeyError, TypeError, ValueError):
                    self.logger.warning(
                        "Failed to parse RacingAndSportsGreyhound race, skipping",
                        meeting=meeting.get("venueName"),
                        race_id=race_summary.get("raceId"),
                        exc_info=True,
                    )
        return all_races

    def _parse_ras_race(
        self, meeting: Dict[str, Any], race: Dict[str, Any]
    ) -> Optional[Race]:
        """Parses a single race object from the API response."""
        race_id = race.get("raceId")
        start_time_str = race.get("startTime")
        if not race_id or not start_time_str:
            return None

        runners = [
            Runner(
                number=rd.get("runnerNumber"),
                name=rd.get("horseName", "Unknown"),
                scratched=rd.get("isScratched", False),
            )
            for rd in race.get("runners", [])
            if isinstance(rd, dict)
        ]

        return Race(
            id=f"rasg_{race_id}",
            venue=meeting.get("venueName", "Unknown Venue"),
            race_number=race.get("raceNumber"),
            start_time=datetime.fromisoformat(start_time_str),
            runners=runners,
            source=self.source_name,
        )
