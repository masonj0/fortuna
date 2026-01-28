"""
Racing Post B2B Widget API Adapter - Production Implementation

A reliable, bot-friendly JSON API that provides comprehensive US race card data.
This adapter integrates with the BaseAdapterV3 architecture and SmartFetcher.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy
from ..models import Race, Runner
from .base_adapter_v3 import BaseAdapterV3


class RacingPostB2BAdapter(BaseAdapterV3):
    """
    Adapter for the Racing Post B2B Widget API.

    This is a clean JSON API that doesn't require any scraping or bot evasion.
    It provides comprehensive race card data for US racing venues.

    Key Features:
    - No bot blocking (public B2B API)
    - Clean JSON format (no HTML parsing)
    - Real-time updates with race status
    - Automatic filtering of abandoned venues/races

    Example API Response Structure:
    [
      {
        "id": "venue-uuid",
        "name": "Parx",
        "countryCode": "USA",
        "isAbandoned": false,
        "races": [
          {
            "id": "race-uuid",
            "datetimeUtc": "2026-01-28T17:05:00+00:00",
            "raceStatusCode": "DEC",
            "numberOfRunners": 12,
            "raceNumber": 1
          }
        ]
      }
    ]
    """

    SOURCE_NAME = "RacingPostB2B"
    BASE_URL = "https://backend-us-racecards.widget.rpb2b.com"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config,
            enable_cache=True,
            cache_ttl=300.0,  # 5 minute cache
            rate_limit=5.0,   # Conservative rate limit
        )

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """
        This is a simple JSON API - HTTPX is perfect.
        No JavaScript, no anti-bot measures, no complexity.
        """
        return FetchStrategy(
            primary_engine=BrowserEngine.HTTPX,
            enable_js=False,
            max_retries=3,
            timeout=20,
        )

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the raw race card data from the Racing Post B2B API.

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            Dictionary containing the race data and metadata, or None if request fails
        """
        endpoint = f"/v2/racecards/daily/{date}"

        try:
            response = await self.make_request("GET", endpoint)

            if not response:
                self.logger.warning("No response from Racing Post B2B API", endpoint=endpoint)
                return None

            data = response.json()

            if not isinstance(data, list):
                self.logger.error(
                    "Unexpected response format - expected list",
                    type=type(data).__name__,
                    endpoint=endpoint
                )
                return None

            # Wrap in dict with metadata for downstream processing
            return {
                "venues": data,
                "date": date,
                "fetched_at": datetime.now().isoformat(),
            }

        except Exception as e:
            self.logger.error(
                "Failed to fetch Racing Post B2B data",
                endpoint=endpoint,
                error=str(e),
                exc_info=True
            )
            return None

    def _parse_races(self, raw_data: Optional[Dict[str, Any]]) -> List[Race]:
        """
        Parses the venue/race data into Race objects.

        Automatically filters out:
        - Abandoned venues (isAbandoned: true)
        - Cancelled/abandoned races (raceStatusCode: "ABD")

        Args:
            raw_data: Dictionary containing venues data and metadata

        Returns:
            List of Race objects
        """
        if not raw_data or not raw_data.get("venues"):
            self.logger.warning("No venues data to parse")
            return []

        venues_data = raw_data["venues"]
        all_races = []

        abandoned_venues = 0
        abandoned_races = 0

        for venue_data in venues_data:
            try:
                # Skip abandoned venues
                if venue_data.get("isAbandoned", False):
                    abandoned_venues += 1
                    self.logger.debug(
                        "Skipping abandoned venue",
                        venue=venue_data.get("name", "Unknown")
                    )
                    continue

                venue_name = venue_data.get("name", "Unknown Venue")
                country_code = venue_data.get("countryCode", "USA")
                races_data = venue_data.get("races", [])

                for race_data in races_data:
                    try:
                        # Skip abandoned/cancelled races
                        if race_data.get("raceStatusCode") == "ABD":
                            abandoned_races += 1
                            self.logger.debug(
                                "Skipping abandoned race",
                                venue=venue_name,
                                race_number=race_data.get("raceNumber")
                            )
                            continue

                        race = self._parse_single_race(race_data, venue_name, country_code)
                        if race:
                            all_races.append(race)

                    except Exception as e:
                        self.logger.warning(
                            "Failed to parse individual race",
                            venue=venue_name,
                            race_id=race_data.get("id"),
                            error=str(e),
                            exc_info=True
                        )
                        continue

            except Exception as e:
                self.logger.warning(
                    "Failed to parse venue data",
                    venue=venue_data.get("name", "Unknown"),
                    error=str(e),
                    exc_info=True
                )
                continue

        self.logger.info(
            "Parsed Racing Post B2B races",
            total_races=len(all_races),
            abandoned_venues=abandoned_venues,
            abandoned_races=abandoned_races
        )

        return all_races

    def _parse_single_race(
        self,
        race_data: dict,
        venue_name: str,
        country_code: str
    ) -> Optional[Race]:
        """
        Parses a single race dictionary into a Race object.

        Args:
            race_data: Dictionary containing race information
            venue_name: Name of the venue
            country_code: Country code (e.g., "USA")

        Returns:
            Race object or None if parsing fails
        """
        # Extract required fields
        race_id = race_data.get("id")
        race_number = race_data.get("raceNumber")
        datetime_str = race_data.get("datetimeUtc")
        num_runners = race_data.get("numberOfRunners", 0)

        if not all([race_id, race_number, datetime_str]):
            self.logger.warning(
                "Missing required race fields",
                race_id=race_id,
                race_number=race_number,
                datetime_str=datetime_str
            )
            return None

        # Parse datetime (format: "2026-01-28T17:05:00+00:00")
        try:
            start_time = datetime.fromisoformat(datetime_str.replace('Z', '+00:00'))
        except (ValueError, TypeError) as e:
            self.logger.error(
                "Failed to parse datetime",
                datetime_str=datetime_str,
                error=str(e)
            )
            return None

        # Create placeholder runners
        # NOTE: This endpoint doesn't provide detailed runner information.
        runners = [
            Runner(
                number=i + 1,
                name=f"Runner {i + 1}",  # Placeholder
                scratched=False,
                odds={}
            )
            for i in range(num_runners)
        ]

        # Generate unique race ID
        race_id_safe = race_id.replace("-", "")[:16]  # Shorten UUID for readability

        return Race(
            id=f"rpb2b_{race_id_safe}",
            venue=venue_name,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
            metadata={
                "original_race_id": race_id,
                "country_code": country_code,
                "race_status": race_data.get("raceStatusCode"),
                "weather": race_data.get("weather"),
                "temperature": race_data.get("temperature"),
                "num_runners": num_runners,
            }
        )
