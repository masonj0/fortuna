# python_service/adapters/greyhound_adapter.py
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from pydantic import ValidationError

from ..core.exceptions import AdapterConfigError
from ..models import OddsData, Race, Runner
from .base_v3 import BaseAdapterV3


class GreyhoundAdapter(BaseAdapterV3):
    """
    Adapter for fetching Greyhound racing data, migrated to BaseAdapterV3.
    Activated by setting GREYHOUND_API_URL in .env.
    """
    SOURCE_NAME = "Greyhound Racing"

    def __init__(self, config=None):
        if not hasattr(config, 'GREYHOUND_API_URL') or not config.GREYHOUND_API_URL:
            raise AdapterConfigError(self.SOURCE_NAME, "GREYHOUND_API_URL is not configured.")
        super().__init__(source_name=self.SOURCE_NAME, base_url=config.GREYHOUND_API_URL, config=config)

    async def _fetch_data(self, date: str) -> Any:
        """Fetches the raw card data from the greyhound API."""
        endpoint = f"v1/cards/{date}"
        response = await self.make_request(self.http_client, "GET", endpoint)
        return response.json() if response else None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses the raw card data into a list of Race objects."""
        if not raw_data or not raw_data.get("cards"):
            self.logger.warning("No 'cards' in greyhound response or empty list.")
            return []

        all_races = []
        for card in raw_data["cards"]:
            venue = card.get("track_name", "Unknown Venue")
            for race_data in card.get("races", []):
                try:
                    if not race_data.get("runners"):
                        continue

                    race = Race(
                        id=f"greyhound_{race_data['race_id']}",
                        venue=venue,
                        race_number=race_data["race_number"],
                        start_time=datetime.fromtimestamp(race_data["start_time"]),
                        runners=self._parse_runners(race_data["runners"]),
                        source=self.source_name,
                    )
                    all_races.append(race)
                except (ValidationError, KeyError) as e:
                    self.logger.error(
                        "Error parsing greyhound race",
                        race_id=race_data.get('race_id', 'N/A'),
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

                odds_data = {}
                win_odds_val = runner_data.get("odds", {}).get("win")
                if win_odds_val is not None:
                    win_odds = Decimal(str(win_odds_val))
                    if win_odds > 1:
                        odds_data[self.source_name] = OddsData(
                            win=win_odds, source=self.source_name, last_updated=datetime.now()
                        )

                runners.append(Runner(
                    number=runner_data["trap_number"],
                    name=runner_data["dog_name"],
                    scratched=runner_data.get("scratched", False),
                    odds=odds_data,
                ))
            except (KeyError, ValidationError):
                self.logger.warning("Error parsing greyhound runner, skipping.", runner_data=runner_data)
                continue
        return runners
