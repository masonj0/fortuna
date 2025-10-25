# python_service/adapters/greyhound_adapter.py
from datetime import datetime
from decimal import Decimal
from typing import Any
from typing import Dict
from typing import List

import httpx
import structlog
from pydantic import ValidationError

from ..core.exceptions import AdapterConfigError
from ..core.exceptions import AdapterParsingError
from ..models import OddsData
from ..models import Race
from ..models import Runner
from .base import BaseAdapter

log = structlog.get_logger(__name__)


class GreyhoundAdapter(BaseAdapter):
    """Adapter for fetching Greyhound racing data. Activated by setting GREYHOUND_API_URL in .env"""

    def __init__(self, config):
        if not config.GREYHOUND_API_URL:
            raise AdapterConfigError(self.source_name, "GREYHOUND_API_URL is not configured.")
        super().__init__(source_name="Greyhound Racing", base_url=config.GREYHOUND_API_URL, config=config)

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> List[Race]:
        """Fetches upcoming greyhound races for the specified date."""
        endpoint = f"v1/cards/{date}"
        response = await self.make_request(http_client, "GET", endpoint)

        response_json = response.json()
        if not response_json or not response_json.get("cards"):
            log.warning("GreyhoundAdapter: No 'cards' in response or empty list.")
            return []

        return self._parse_cards(response_json["cards"])

    def _parse_cards(self, cards: List[Dict[str, Any]]) -> List[Race]:
        """Parses a list of cards and their races into Race objects."""
        all_races = []
        if cards is None:
            return all_races
        for card in cards:
            venue = card.get("track_name", "Unknown Venue")
            races_data = card.get("races", [])
            for race_data in races_data:
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
                    log.error(
                        f"GreyhoundAdapter: Error parsing race {race_data.get('race_id', 'N/A')}",
                        error=str(e),
                        race_data=race_data,
                    )
                    raise AdapterParsingError(
                        self.source_name,
                        f"Failed to parse race: {race_data.get('race_id')}",
                    ) from e
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
                log.warning("GreyhoundAdapter: Error parsing runner, skipping.", runner_data=runner_data)
                continue
        return runners
