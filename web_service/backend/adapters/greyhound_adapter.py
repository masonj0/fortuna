# python_service/adapters/greyhound_adapter.py
from datetime import datetime
from decimal import Decimal
from typing import Any
from typing import Dict
from typing import List

from pydantic import ValidationError

from ..core.exceptions import AdapterConfigError
from ..models import OddsData
from ..models import Race
from ..models import Runner
from .base_adapter_v3 import BaseAdapterV3


class GreyhoundAdapter(BaseAdapterV3):
    """
    Adapter for fetching Greyhound racing data, migrated to BaseAdapterV3.
    Activated by setting GREYHOUND_API_URL in .env.
    """

    SOURCE_NAME = "Greyhound Racing"

    def __init__(self, config=None):
        if not hasattr(config, "GREYHOUND_API_URL") or not config.GREYHOUND_API_URL:
            raise AdapterConfigError(self.SOURCE_NAME, "GREYHOUND_API_URL is not configured.")
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=config.GREYHOUND_API_URL,
            config=config,
        )

    async def _fetch_data(self, date: str) -> Any:
        """Fetches the raw card data from the greyhound API."""
        endpoint = f"v1/cards/{date}"
        response = await self.make_request("GET", endpoint)
        return response.json() if response else None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses the raw card data into a list of Race objects."""
        if not raw_data or not raw_data.get("cards"):
            self.logger.warning("No 'cards' in greyhound response or empty list.")
            return []

        all_races = []
        for card in raw_data.get("cards", []):
            venue = card.get("track_name", "Unknown Venue")
            for race_data in card.get("races", []):
                try:
                    if not race_data.get("runners"):
                        continue

                    race_id = race_data.get("race_id")
                    race_number = race_data.get("race_number")
                    start_timestamp = race_data.get("start_time")
                    if not all([race_id, race_number, start_timestamp]):
                        continue

                    race = Race(
                        id=f"greyhound_{race_id}",
                        venue=venue,
                        race_number=race_number,
                        start_time=datetime.fromtimestamp(start_timestamp),
                        runners=self._parse_runners(race_data.get("runners", [])),
                        source=self.source_name,
                    )
                    all_races.append(race)
                except (ValidationError, KeyError) as e:
                    self.logger.error(
                        "Error parsing greyhound race",
                        race_id=race_data.get("race_id", "N/A"),
                        error=str(e),
                    )
                    continue
        return all_races

    def _parse_runners(self, runners_data: List[Dict[str, Any]]) -> List[Runner]:
        """Parses a list of runner dictionaries into Runner objects."""
        runners = []
        for runner_data in runners_data:
            try:
                if runner_data.get("scratched", False):
                    continue

                trap_number = runner_data.get("trap_number")
                dog_name = runner_data.get("dog_name")
                if not all([trap_number, dog_name]):
                    continue

                odds_data = {}
                win_odds_val = runner_data.get("odds", {}).get("win")
                if win_odds_val is not None:
                    win_odds = Decimal(str(win_odds_val))
                    if win_odds > 1:
                        odds_data[self.source_name] = OddsData(
                            win=win_odds,
                            source=self.source_name,
                            last_updated=datetime.now(),
                        )

                runners.append(
                    Runner(
                        number=trap_number,
                        name=dog_name,
                        scratched=runner_data.get("scratched", False),
                        odds=odds_data,
                    )
                )
            except (KeyError, ValidationError):
                self.logger.warning("Error parsing greyhound runner, skipping.", runner_data=runner_data)
                continue
        return runners
