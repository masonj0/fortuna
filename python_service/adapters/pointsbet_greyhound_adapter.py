# python_service/adapters/pointsbet_greyhound_adapter.py
from typing import Any, List, Optional, Dict
from ..models import Race, Runner, OddsData
from .base_v3 import BaseAdapterV3
from datetime import datetime
from decimal import Decimal

# NOTE: This is a hypothetical implementation based on a potential API structure.


class PointsBetGreyhoundAdapter(BaseAdapterV3):
    """Adapter for the hypothetical PointsBet Greyhound API, migrated to BaseAdapterV3."""

    SOURCE_NAME = "PointsBetGreyhound"
    BASE_URL = "https://api.pointsbet.com/api/v2/"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config
        )

    async def _fetch_data(self, date: str) -> Optional[List[Dict[str, Any]]]:
        """Fetches all greyhound events for a given date."""
        endpoint = f"sports/greyhound-racing/events/by-date/{date}"
        response = await self.make_request(self.http_client, "GET", endpoint)
        return response.json().get("events", []) if response else None

    def _parse_races(self, raw_data: Optional[List[Dict[str, Any]]]) -> List[Race]:
        """Parses the raw event data into a list of standardized Race objects."""
        if not raw_data:
            return []

        races = []
        for event in raw_data:
            try:
                if not event.get("competitors") or not event.get("startTime"):
                    continue

                runners = []
                for competitor in event.get("competitors", []):
                    price = competitor.get("price")
                    if not price:
                        continue

                    odds_val = Decimal(str(price))
                    odds = {
                        self.source_name: OddsData(
                            win=odds_val,
                            source=self.source_name,
                            last_updated=datetime.now(),
                        )
                    }
                    runner = Runner(
                        number=competitor.get("number", 99),
                        name=competitor.get("name", "Unknown"),
                        odds=odds,
                    )
                    runners.append(runner)

                if runners:
                    race_id = event.get("id")
                    if not race_id:
                        continue

                    race = Race(
                        id=f"pbg_{race_id}",
                        venue=event.get("venue", {}).get("name", "Unknown Venue"),
                        start_time=datetime.fromisoformat(event["startTime"]),
                        race_number=event.get("raceNumber", 1),
                        runners=runners,
                        source=self.source_name,
                    )
                    races.append(race)
            except (KeyError, TypeError, ValueError):
                self.logger.warning(
                    "Failed to parse PointsBet Greyhound event.",
                    event=event,
                    exc_info=True,
                )
                continue
        return races
