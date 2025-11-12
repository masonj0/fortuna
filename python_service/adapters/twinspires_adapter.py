# python_service/adapters/twinspires_adapter.py
from typing import Any
from typing import List

from ..models import Race
from .base_adapter_v3 import BaseAdapterV3


class TwinSpiresAdapter(BaseAdapterV3):
    """
    Adapter for twinspires.com.
    This is a placeholder for a full implementation using the discovered JSON API.
    """

    SOURCE_NAME = "TwinSpires"
    BASE_URL = "https://www.twinspires.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Any:
        """
        Fetches all race data for a given date from the Twinspires JSON API.
        It first fetches a list of all tracks, then fetches the race card for each track.
        """
        import asyncio
        self.logger.info("Fetching track list from TwinSpires")
        tracks_url = "adw/todays-tracks?affid=0"
        tracks_response = await self.make_request(self.http_client, "GET", tracks_url)
        if not tracks_response:
            return None

        tracks_data = tracks_response.json()
        self.logger.info(f"Found {len(tracks_data)} tracks. Fetching race cards.")

        race_card_tasks = []
        for track in tracks_data:
            track_id = track.get("trackId")
            race_type = track.get("raceType")
            if track_id and race_type:
                url = f"adw/todays-tracks/{track_id}/{race_type}/races?affid=0"
                race_card_tasks.append(self.make_request(self.http_client, "GET", url))

        race_card_responses = await asyncio.gather(*race_card_tasks, return_exceptions=True)

        # Filter out exceptions and return only successful responses, including track info
        results = []
        for track, resp in zip(tracks_data, race_card_responses):
            if resp and not isinstance(resp, Exception):
                results.append({"track": track, "races": resp.json()})

        return results

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """
        Parses the JSON data from the Twinspires API into Race objects.
        """
        from datetime import datetime
        if not raw_data:
            return []

        self.logger.info("Parsing TwinSpires race data.")
        races = []
        for track_data in raw_data:
            track = track_data.get("track", {})
            race_cards = track_data.get("races", [])

            for race_card in race_cards:
                try:
                    start_time = datetime.fromisoformat(race_card.get("postTime").replace("Z", "+00:00"))

                    # TODO: Find the API endpoint for runner data.
                    # The runner data is not included in the race card, so a third API call
                    # will be needed here to get the runners for each race.
                    # For now, we will create the race with an empty runners list.

                    races.append(
                        Race(
                            id=f"ts_{track.get('trackId')}_{race_card.get('raceNumber')}",
                            venue=track.get("trackName"),
                            race_number=race_card.get("raceNumber"),
                            start_time=start_time,
                            discipline=track.get("raceType", "Unknown"),
                            runners=[], # Placeholder
                            source=self.SOURCE_NAME,
                        )
                    )
                except Exception as e:
                    self.logger.warning(
                        "Failed to parse race card, skipping.",
                        race_card=race_card,
                        error=e,
                        exc_info=True,
                    )

        return races

    async def _get_races_async(self, date: str) -> List[Race]:
        raw_data = await self._fetch_data(date)
        return self._parse_races(raw_data)

    def get_races(self, date: str) -> List[Race]:
        """
        Orchestrates the fetching and parsing of race data for a given date.
        This method will be called by the FortunaEngine.
        """
        self.logger.info(f"Getting races for {date} from {self.SOURCE_NAME}")
        # This is a synchronous wrapper for the async orchestrator
        # It's a temporary measure to allow me to see the API response.
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        races = loop.run_until_complete(self._get_races_async(date))
        return races
