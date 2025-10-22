# python_service/adapters/racing_and_sports_greyhound_adapter.py

from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
import structlog

from ..core.exceptions import AdapterConfigError, AdapterParsingError
from ..models import Race, Runner
from .base import BaseAdapter

log = structlog.get_logger(__name__)


class RacingAndSportsGreyhoundAdapter(BaseAdapter):
    def __init__(self, config):
        super().__init__(source_name="Racing and Sports Greyhound", base_url="https://api.racingandsports.com.au/")
        if not hasattr(config, "RACING_AND_SPORTS_TOKEN") or not config.RACING_AND_SPORTS_TOKEN:
            raise AdapterConfigError(self.source_name, "RACING_AND_SPORTS_TOKEN is not configured.")
        self.api_token = config.RACING_AND_SPORTS_TOKEN

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> List[Race]:
        headers = {"Authorization": f"Bearer {self.api_token}", "Accept": "application/json"}
        meetings_url = "v1/greyhound/meetings"
        params = {"date": date, "jurisdiction": "AUS"}

        meetings_response = await self.make_request(http_client, "GET", meetings_url, headers=headers, params=params)

        try:
            meetings_data = meetings_response.json()
            if not meetings_data or not meetings_data.get("meetings"):
                log.warning("No greyhound meetings found in RacingAndSports response.")
                return []

            all_races = []
            for meeting in meetings_data["meetings"]:
                for race_summary in meeting.get("races", []):
                    try:
                        if parsed_race := self._parse_ras_race(meeting, race_summary):
                            all_races.append(parsed_race)
                    except (KeyError, TypeError, ValueError) as e:
                        log.warning(
                            "RacingAndSportsGreyhoundAdapter: Failed to parse race, skipping",
                            meeting=meeting.get("venueName"),
                            race_id=race_summary.get("raceId"),
                            error=str(e),
                        )
            return all_races
        except (ValueError, TypeError) as e:
            log.error("RacingAndSportsGreyhoundAdapter: Failed to parse response JSON", error=str(e))
            raise AdapterParsingError(self.source_name, "Failed to parse API response JSON.") from e

    def _parse_ras_race(self, meeting: Dict[str, Any], race: Dict[str, Any]) -> Optional[Race]:
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
        ]

        return Race(
            id=f"rasg_{race_id}",
            venue=meeting.get("venueName", "Unknown Venue"),
            race_number=race.get("raceNumber"),
            start_time=datetime.fromisoformat(start_time_str),
            runners=runners,
            source=self.source_name,
        )
