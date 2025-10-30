# python_service/adapters/tvg_adapter.py
import asyncio
from datetime import datetime
from typing import Any, List

from ..core.exceptions import AdapterConfigError, AdapterParsingError
from ..models import Race, Runner
from ..utils.text import clean_text
from .base_v3 import BaseAdapterV3


class TVGAdapter(BaseAdapterV3):
    """Adapter for fetching US racing data from the TVG API, migrated to BaseAdapterV3."""

    SOURCE_NAME = "TVG"
    BASE_URL = "https://api.tvg.com/v2/races/"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config
        )
        if not hasattr(config, "TVG_API_KEY") or not config.TVG_API_KEY:
            raise AdapterConfigError(self.source_name, "TVG_API_KEY is not configured.")
        self.tvg_api_key = config.TVG_API_KEY

    async def _fetch_data(self, date: str) -> Any:
        """Fetches all race details for a given date by first getting tracks."""
        headers = {"X-Api-Key": self.tvg_api_key}
        summary_url = f"summary?date={date}&country=USA"

        tracks_response = await self.make_request(
            self.http_client, "GET", summary_url, headers=headers
        )
        if not tracks_response:
            return None
        tracks_data = tracks_response.json()

        race_detail_tasks = []
        for track in tracks_data.get("tracks", []):
            track_id = track.get("id")
            for race in track.get("races", []):
                race_id = race.get("id")
                if track_id and race_id:
                    details_url = f"{track_id}/{race_id}"
                    race_detail_tasks.append(
                        self.make_request(
                            self.http_client, "GET", details_url, headers=headers
                        )
                    )

        race_detail_responses = await asyncio.gather(
            *race_detail_tasks, return_exceptions=True
        )

        # Filter out exceptions and return only successful responses
        return [
            resp.json()
            for resp in race_detail_responses
            if not isinstance(resp, Exception)
        ]

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses a list of detailed race JSON objects into Race models."""
        races = []
        if not isinstance(raw_data, list):
            self.logger.warning("raw_data is not a list, cannot parse TVG races.")
            return races

        for race_detail in raw_data:
            try:
                races.append(self._parse_race(race_detail))
            except AdapterParsingError:
                self.logger.warning(
                    "Failed to parse TVG race detail, skipping.",
                    race_detail=race_detail,
                    exc_info=True,
                )
        return races

    def _parse_race(self, race_detail: dict) -> Race:
        """Parses a single detailed race JSON object into a Race model."""
        track = race_detail.get("track")
        race_info = race_detail.get("race")

        if not track or not race_info:
            raise AdapterParsingError(
                self.source_name, "Missing track or race info in race detail."
            )

        runners = []
        for runner_data in race_detail.get("runners", []):
            if runner_data.get("scratched"):
                continue

            odds = runner_data.get("odds", {})
            current_odds = odds.get("currentPrice", {})
            odds_str = current_odds.get("fractional") or odds.get(
                "morningLinePrice", {}
            ).get("fractional")

            try:
                number = int(runner_data.get("programNumber", "0").replace("A", ""))
            except (ValueError, TypeError):
                self.logger.warning(
                    f"Could not parse program number: {runner_data.get('programNumber')}"
                )
                continue

            runners.append(
                Runner(
                    number=number,
                    name=clean_text(runner_data.get("name")),
                    odds=odds_str,  # Odds will be parsed later in the data pipeline
                    scratched=False,
                )
            )

        if not runners:
            raise AdapterParsingError(
                self.source_name, "No non-scratched runners found."
            )

        try:
            start_time = datetime.fromisoformat(
                race_info.get("postTime").replace("Z", "+00:00")
            )
        except (ValueError, TypeError, AttributeError) as e:
            raise AdapterParsingError(
                self.source_name,
                f"Could not parse post time: {race_info.get('postTime')}",
            ) from e

        return Race(
            id=f"tvg_{track.get('code', 'UNK')}_{race_info.get('date', 'NODATE')}_{race_info.get('number', 0)}",
            venue=track.get("name"),
            race_number=race_info.get("number"),
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )
