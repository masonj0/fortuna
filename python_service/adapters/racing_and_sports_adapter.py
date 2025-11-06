# python_service/adapters/racing_and_sports_adapter.py

from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

from ..core.exceptions import AdapterConfigError
from ..models import Race
from ..models import Runner
from .base_v3 import BaseAdapterV3


class RacingAndSportsAdapter(BaseAdapterV3):
    """Adapter for Racing and Sports API, migrated to BaseAdapterV3."""

    SOURCE_NAME = "RacingAndSports"
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
        """Fetches the raw meetings data from the Racing and Sports API."""
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Accept": "application/json",
        }
        params = {"date": date, "jurisdiction": "AUS"}
        response = await self.make_request(
            self.http_client,
            "GET",
            "v1/racing/meetings",
            headers=headers,
            params=params,
        )
        return response.json() if response else None

    def _parse_races(self, raw_data: Optional[Dict[str, Any]]) -> List[Race]:
        """Parses the raw meetings data into a list of Race objects."""
        all_races = []
        if not raw_data or not isinstance(raw_data.get("meetings"), list):
            self.logger.warning(
                "No 'meetings' in RacingAndSports response or invalid format."
            )
            return all_races

        for meeting in raw_data.get("meetings", []):
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
                        "Failed to parse RacingAndSports race, skipping",
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
        race_number = race.get("raceNumber")

        if not all([race_id, start_time_str, race_number]):
            return None

        runners = [
            Runner(
                number=rd.get("runnerNumber", 0),
                name=rd.get("horseName", "Unknown"),
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
                "Invalid start time format for RacingAndSports race",
                start_time_str=start_time_str,
                race_id=race_id,
            )
            return None

        return Race(
            id=f"ras_{race_id}",
            venue=meeting.get("venueName", "Unknown Venue"),
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )
