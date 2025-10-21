# python_service/adapters/racing_and_sports_adapter.py

from datetime import datetime
from typing import Any
from typing import Dict
from typing import List

import httpx
import structlog

from ..models import Race
from ..models import Runner
from .base import BaseAdapter

log = structlog.get_logger(__name__)


class RacingAndSportsAdapter(BaseAdapter):
    def __init__(self, config):
        super().__init__(source_name="Racing and Sports", base_url="https://api.racingandsports.com.au/")
        self.api_token = config.RACING_AND_SPORTS_TOKEN

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> Dict[str, Any]:
        start_time = datetime.now()
        headers = {"Authorization": f"Bearer {self.api_token}", "Accept": "application/json"}

        if not self.api_token:
            return self._format_response([], start_time, is_success=False, error_message="ConfigurationError: Token not set")

        meetings_url = "v1/racing/meetings"
        params = {"date": date, "jurisdiction": "AUS"}
        meetings_response = await self.make_request(http_client, "GET", meetings_url, headers=headers, params=params)

        if not meetings_response:
            return self._format_response([], start_time, is_success=False, error_message="API request failed")

        try:
            meetings_data = meetings_response.json()
            all_races = self._parse_races(meetings_data)
            return self._format_response(all_races, start_time, is_success=True)
        except Exception as e:
            log.error("RacingAndSportsAdapter: Failed to parse response JSON", error=str(e), exc_info=True)
            return self._format_response([], start_time, is_success=False, error_message="Failed to parse API response")

    def _parse_races(self, meetings_data: Dict[str, Any]) -> List[Race]:
        all_races = []
        if not meetings_data or not isinstance(meetings_data.get("meetings"), list):
            return all_races

        for meeting in meetings_data["meetings"]:
            if not isinstance(meeting, dict):
                continue
            for race_summary in meeting.get("races", []):
                if not isinstance(race_summary, dict):
                    continue
                try:
                    parsed_race = self._parse_ras_race(meeting, race_summary)
                    if parsed_race:
                        all_races.append(parsed_race)
                except (KeyError, TypeError, ValueError) as e:
                    log.warning(
                        "RacingAndSportsAdapter: Failed to parse race, skipping",
                        meeting=meeting.get("venueName"),
                        race_id=race_summary.get("raceId"),
                        error=str(e),
                    )
        return all_races

    def _format_response(self, races: List[Race], start_time: datetime, is_success: bool = True, error_message: str = None) -> Dict[str, Any]:
        fetch_duration = (datetime.now() - start_time).total_seconds()
        return {
            "races": races,
            "source_info": {
                "name": self.source_name,
                "status": "SUCCESS" if is_success else "FAILED",
                "races_fetched": len(races),
                "error_message": error_message,
                "fetch_duration": fetch_duration,
            },
        }

    def _parse_ras_race(self, meeting: Dict[str, Any], race: Dict[str, Any]) -> Race:
        race_id = race.get("raceId")
        if not race_id:
            return None

        runners = []
        for rd in race.get("runners", []):
            if not isinstance(rd, dict):
                continue
            runners.append(
                Runner(
                    number=rd.get("runnerNumber"),
                    name=rd.get("horseName", "Unknown"),
                    scratched=rd.get("isScratched", False),
                )
            )

        start_time_str = race.get("startTime")
        if not start_time_str:
            return None
        start_time = datetime.fromisoformat(start_time_str)

        return Race(
            id=f"ras_{race_id}",
            venue=meeting.get("venueName", "Unknown Venue"),
            race_number=race.get("raceNumber"),
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )
