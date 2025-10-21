# python_service/adapters/tvg_adapter.py
from datetime import datetime
from typing import List
import httpx
import asyncio

from ..core.exceptions import AdapterConfigError, AdapterParsingError
from ..models import Race, Runner
from ..utils.text import clean_text
from .base import BaseAdapter

class TVGAdapter(BaseAdapter):
    """Adapter for fetching US racing data from the TVG API."""

    def __init__(self, config):
        super().__init__(source_name="TVG", base_url="https://api.tvg.com/v2/races/", config=config)
        if not hasattr(config, "TVG_API_KEY") or not config.TVG_API_KEY:
            raise AdapterConfigError(self.source_name, "TVG_API_KEY is not configured.")
        self.tvg_api_key = config.TVG_API_KEY

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> List[Race]:
        """Fetches all race details for a given date by first getting tracks."""
        headers = {"X-Api-Key": self.tvg_api_key}
        summary_url = f"summary?date={date}&country=USA"

        tracks_response = await self.make_request(http_client, "GET", summary_url, headers=headers)
        tracks_data = tracks_response.json()

        race_detail_tasks = []
        for track in tracks_data.get('tracks', []):
            track_id = track.get('id')
            for race in track.get('races', []):
                race_id = race.get('id')
                if track_id and race_id:
                    details_url = f"{track_id}/{race_id}"
                    race_detail_tasks.append(self.make_request(http_client, "GET", details_url, headers=headers))

        race_detail_responses = await asyncio.gather(*race_detail_tasks, return_exceptions=True)

        races = []
        for response in race_detail_responses:
            if isinstance(response, Exception):
                self.logger.error("Failed to fetch race detail", error=response)
                continue
            try:
                races.append(self._parse_race(response.json()))
            except AdapterParsingError as e:
                self.logger.error("Failed to parse TVG race detail", error=e)

        return races


    def _parse_race(self, race_detail: dict) -> Race:
        """Parses a single detailed race JSON object into a Race model."""
        track = race_detail.get('track')
        race_info = race_detail.get('race')

        if not track or not race_info:
            raise AdapterParsingError(self.source_name, "Missing track or race info in race detail.")

        runners = []
        for runner_data in race_detail.get('runners', []):
            if runner_data.get('scratched'):
                continue

            odds = runner_data.get('odds', {})
            current_odds = odds.get('currentPrice', {})
            odds_str = current_odds.get('fractional') or odds.get('morningLinePrice', {}).get('fractional')

            try:
                number = int(runner_data.get('programNumber', '0').replace('A', ''))
            except (ValueError, TypeError):
                self.logger.warning(f"Could not parse program number: {runner_data.get('programNumber')}")
                continue

            runners.append(Runner(
                number=number,
                name=clean_text(runner_data.get('name')),
                odds=odds_str,
                scratched=False
            ))

        if not runners:
            raise AdapterParsingError(self.source_name, "No non-scratched runners found.")

        try:
            start_time = datetime.fromisoformat(race_info.get('postTime').replace('Z', '+00:00'))
        except (ValueError, TypeError, AttributeError) as e:
            raise AdapterParsingError(self.source_name, f"Could not parse post time: {race_info.get('postTime')}") from e

        return Race(
            id=f"tvg_{track.get('code', 'UNK')}_{race_info.get('date', 'NODATE')}_{race_info.get('number', 0)}",
            venue=track.get('name'),
            race_number=race_info.get('number'),
            start_time=start_time,
            runners=runners,
            source=self.source_name
        )
