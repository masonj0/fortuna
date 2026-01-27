# python_service/adapters/xpressbet_adapter.py

from datetime import datetime
from typing import Any, Dict, List, Optional

from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy
from ..core.exceptions import AdapterConfigError
from ..models import Race, Runner
from .base_adapter_v3 import BaseAdapterV3
from .utils.odds_validator import create_odds_data


class XpressbetAdapter(BaseAdapterV3):
    """
    Adapter for Xpressbet API, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "Xpressbet"
    BASE_URL = "https://api.xpressbet.com/v1/"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)
        if not getattr(config, "XPRESSBET_API_KEY", None):
            # Many adapters are skipped if not configured, this is standard.
            self.api_key = None
        else:
            self.api_key = config.XPRESSBET_API_KEY

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        """Fetches the raw meetings data from the Xpressbet API."""
        if not self.api_key:
            self.logger.warning("Xpressbet API key not configured, skipping fetch.")
            return None

        headers = {"Authorization": f"Bearer {self.api_key}"}
        response = await self.make_request("GET", f"meetings?date={date}", headers=headers)
        return response.json() if response else None

    def _parse_races(self, raw_data: Optional[Dict[str, Any]]) -> List[Race]:
        """Parses the raw meetings data into a list of Race objects."""
        if not raw_data or not isinstance(raw_data.get("meetings"), list):
            return []

        all_races = []
        for meeting in raw_data.get("meetings", []):
            venue = meeting.get("name")
            for race_data in meeting.get("races", []):
                try:
                    if race := self._parse_race(race_data, venue):
                        all_races.append(race)
                except (KeyError, TypeError, ValueError):
                    self.logger.error(
                        "Error parsing Xpressbet race",
                        race_id=race_data.get("id"),
                        exc_info=True,
                    )
                    continue
        return all_races

    def _parse_race(self, race_data: Dict[str, Any], venue: str) -> Optional[Race]:
        """Parses a single race object from the API response."""
        race_id = race_data.get("id")
        race_number = race_data.get("number")
        start_time_str = race_data.get("startTime")

        if not all([race_id, race_number, start_time_str]):
            return None

        runners = []
        for runner_data in race_data.get("runners", []):
            name = runner_data.get("name")
            number = runner_data.get("number")
            if not all([name, number]):
                continue

            runners.append(
                Runner(
                    name=name,
                    number=number,
                    scratched=runner_data.get("scratched", False),
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
            id=f"xb_{race_id}",
            venue=venue,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )
