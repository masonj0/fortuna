# python_service/adapters/theracingapi_adapter.py

from datetime import datetime
from decimal import Decimal
from typing import Any
from typing import Dict
from typing import List

import httpx
import structlog

from ..core.exceptions import AdapterConfigError
from ..models import OddsData
from ..models import Race
from ..models import Runner
from .base import BaseAdapter

log = structlog.get_logger(__name__)


class TheRacingApiAdapter(BaseAdapter):
    """Adapter for the high-value JSON-based The Racing API."""

    def __init__(self, config):
        super().__init__(
            source_name="TheRacingAPI",
            base_url="https://api.theracingapi.com/v1/",
            config=config,
        )
        if not hasattr(config, "THE_RACING_API_KEY") or not config.THE_RACING_API_KEY:
            raise AdapterConfigError(self.source_name, "THE_RACING_API_KEY is not configured.")
        self.api_key = config.THE_RACING_API_KEY

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> List[Race]:
        """
        Fetches race data from The Racing API and parses it into Race objects.

        Raises:
            AdapterError: If the request fails or the response is invalid.
        """
        endpoint = f"racecards?date={date}&course=all&region=gb,ire"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        # make_request will now raise an exception on failure, which will be handled
        # by the upstream service (e.g., the main engine).
        response = await self.make_request(http_client, "GET", endpoint, headers=headers)

        response_json = response.json()
        if not response_json or "racecards" not in response_json:
            log.warning(f"{self.source_name}: 'racecards' key missing in API response.")
            return []

        return self._parse_races(response_json["racecards"])

    def _parse_races(self, racecards: List[Dict[str, Any]]) -> List[Race]:
        races = []
        for race_data in racecards:
            try:
                start_time = datetime.fromisoformat(race_data["off_time"].replace("Z", "+00:00"))

                race = Race(
                    id=f"tra_{race_data['race_id']}",
                    venue=race_data["course"],
                    race_number=race_data["race_no"],
                    start_time=start_time,
                    runners=self._parse_runners(race_data.get("runners", [])),
                    source=self.source_name,
                    race_name=race_data.get("race_name"),
                    distance=race_data.get("distance_f"),
                )
                races.append(race)
            except Exception as e:
                log.error(f"{self.source_name}: Error parsing race", race_id=race_data.get("race_id"), error=str(e))
        return races

    def _parse_runners(self, runners_data: List[Dict[str, Any]]) -> List[Runner]:
        runners = []
        for i, runner_data in enumerate(runners_data):
            try:
                odds_data = {}
                if runner_data.get("odds"):
                    win_odds = Decimal(str(runner_data["odds"][0]["odds_decimal"]))
                    odds_data[self.source_name] = OddsData(
                        win=win_odds, source=self.source_name, last_updated=datetime.now()
                    )

                runners.append(
                    Runner(
                        number=runner_data.get("number", i + 1),
                        name=runner_data["horse"],
                        odds=odds_data,
                        jockey=runner_data.get("jockey"),
                        trainer=runner_data.get("trainer"),
                    )
                )
            except Exception as e:
                log.error(
                    f"{self.source_name}: Error parsing runner", runner_name=runner_data.get("horse"), error=str(e)
                )
        return runners

    def _format_response(
        self, races: List[Race], start_time: datetime, is_success: bool = True, error_message: str = None
    ) -> Dict[str, Any]:
        return {
            "races": races,
            "source_info": {
                "name": self.source_name,
                "status": "SUCCESS" if is_success else "FAILED",
                "races_fetched": len(races),
                "error_message": error_message,
                "fetch_duration": (datetime.now() - start_time).total_seconds(),
            },
        }
