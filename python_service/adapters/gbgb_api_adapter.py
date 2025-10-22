# python_service/adapters/gbgb_api_adapter.py

from datetime import datetime
from typing import Any, Dict, List

import httpx
import structlog

from ..core.exceptions import AdapterParsingError
from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal
from .base import BaseAdapter

log = structlog.get_logger(__name__)


class GbgbApiAdapter(BaseAdapter):
    """Adapter for the undocumented JSON API for the Greyhound Board of Great Britain."""

    def __init__(self, config):
        super().__init__(source_name="GBGB", base_url="https://api.gbgb.org.uk/api/", config=config)

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> List[Race]:
        endpoint = f"results/meeting/{date}"
        response = await self.make_request(http_client, "GET", endpoint)

        if not response:
            return []

        return self._parse_meetings(response.json())

    def _parse_meetings(self, meetings_data: List[Dict[str, Any]]) -> List[Race]:
        races = []
        if meetings_data is None:
            return races
        for meeting in meetings_data:
            track_name = meeting.get("trackName")
            for race_data in meeting.get("races", []):
                try:
                    races.append(self._parse_race(race_data, track_name))
                except (KeyError, TypeError) as e:
                    log.error(f"{self.source_name}: Error parsing race", race_id=race_data.get("raceId"), error=str(e))
                    raise AdapterParsingError(self.source_name, f"Failed to parse race: {race_data.get('raceId')}") from e
        return races

    def _parse_race(self, race_data: Dict[str, Any], track_name: str) -> Race:
        return Race(
            id=f"gbgb_{race_data['raceId']}",
            venue=track_name,
            race_number=race_data["raceNumber"],
            start_time=datetime.fromisoformat(race_data["raceTime"].replace("Z", "+00:00")),
            runners=self._parse_runners(race_data.get("traps", [])),
            source=self.source_name,
            race_name=race_data.get("raceTitle"),
            distance=f"{race_data.get('raceDistance')}m",
        )

    def _parse_runners(self, runners_data: List[Dict[str, Any]]) -> List[Runner]:
        runners = []
        for runner_data in runners_data:
            try:
                odds_data = {}
                sp = runner_data.get("sp")
                win_odds = parse_odds_to_decimal(sp)
                if win_odds and win_odds < 999:
                    odds_data[self.source_name] = OddsData(
                        win=win_odds, source=self.source_name, last_updated=datetime.now()
                    )

                runners.append(
                    Runner(
                        number=runner_data["trapNumber"],
                        name=runner_data["dogName"],
                        odds=odds_data,
                    )
                )
            except (KeyError, TypeError):
                log.warning(f"{self.source_name}: Error parsing runner", runner_name=runner_data.get("dogName"))
                # Skip runner, but don't fail the whole race
                continue
        return runners
