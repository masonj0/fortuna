from typing import List

import httpx

from ..models import Race
from ..models import Runner
from .base import BaseAdapter

# NOTE: This is a hypothetical implementation based on a potential API structure.

class PointsBetGreyhoundAdapter(BaseAdapter):
    def __init__(self, config: dict):
        super().__init__(source_name="PointsBetGreyhound", base_url="https://api.pointsbet.com/api/v2/", config=config)

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> List[Race]:
        """Fetches all greyhound events for a given date from the hypothetical PointsBet API."""
        endpoint = f'sports/greyhound-racing/events/by-date/{date}'
        response = await self.make_request(http_client, "GET", endpoint)
        raw_data = response.json().get('events', [])
        return self._parse_races(raw_data)

    def _parse_races(self, raw_data: list) -> List[Race]:
        """Parses the raw event data into a list of standardized Race objects."""
        races = []
        for event in raw_data:
            if not event.get('competitors') or not event.get('startTime'):
                continue

            runners = []
            for competitor in event.get('competitors', []):
                if competitor.get('price'):
                    runner = Runner(
                        number=competitor.get('number', 99),
                        name=competitor.get('name', 'Unknown'),
                        odds={'win': float(competitor['price'])}
                    )
                    runners.append(runner)

            if runners:
                race = Race(
                    id=f'pbg_{event["id"]}',
                    venue=event.get('venue', {}).get('name', 'Unknown Venue'),
                    start_time=event['startTime'],
                    race_number=event.get('raceNumber', 1),
                    runners=runners,
                    source=self.source_name,
                )
                races.append(race)
        return races
