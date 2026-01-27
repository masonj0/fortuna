from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy
# python_service/adapters/betfair_greyhound_adapter.py
import re
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import List
from typing import Optional

from ..models import Race
from ..models import Runner
from .base_adapter_v3 import BaseAdapterV3
from .betfair_auth_mixin import BetfairAuthMixin


class BetfairGreyhoundAdapter(BetfairAuthMixin, BaseAdapterV3):
    """Adapter for fetching greyhound racing data from the Betfair Exchange API, using V3 architecture."""

    SOURCE_NAME = "BetfairGreyhounds"
    BASE_URL = "https://api.betfair.com/exchange/betting/rest/v1.0/"

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Any:
        """Fetches the raw market catalogue for greyhound races on a given date."""
        await self._authenticate(self.http_client)
        if not self.session_token:
            self.logger.error("Authentication failed, cannot fetch data.")
            return None

        start_time, end_time = self._get_datetime_range(date)

        response = await self.make_request(
            self.http_client,
            method="post",
            url=f"{self.BASE_URL}listMarketCatalogue/",
            json={
                "filter": {
                    "eventTypeIds": ["4339"],  # Greyhound Racing
                    "marketCountries": ["GB", "IE", "AU"],
                    "marketTypeCodes": ["WIN"],
                    "marketStartTime": {
                        "from": start_time.isoformat(),
                        "to": end_time.isoformat(),
                    },
                },
                "maxResults": 1000,
                "marketProjection": ["EVENT", "RUNNER_DESCRIPTION"],
            },
        )
        return response.json() if response else None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses the raw market catalogue into a list of Race objects."""
        if not raw_data:
            return []

        races = []
        for market in raw_data:
            try:
                if race := self._parse_race(market):
                    races.append(race)
            except (KeyError, TypeError):
                self.logger.warning(
                    "Failed to parse a Betfair Greyhound market.",
                    exc_info=True,
                    market=market,
                )
                continue
        return races

    def _parse_race(self, market: dict) -> Optional[Race]:
        """Parses a single market from the Betfair API into a Race object."""
        market_id = market.get("marketId")
        event = market.get("event", {})
        market_start_time = market.get("marketStartTime")

        if not all([market_id, market_start_time]):
            return None

        start_time = datetime.fromisoformat(market_start_time.replace("Z", "+00:00"))

        runners = [
            Runner(
                number=runner.get("sortPriority", i + 1),
                name=runner.get("runnerName"),
                scratched=runner.get("status") != "ACTIVE",
                selection_id=runner.get("selectionId"),
            )
            for i, runner in enumerate(market.get("runners", []))
            if runner.get("runnerName")
        ]

        return Race(
            id=f"bfg_{market_id}",
            venue=event.get("venue", "Unknown Venue"),
            race_number=self._extract_race_number(market.get("marketName", "")),
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )

    def _extract_race_number(self, name: str) -> int:
        """Extracts the race number from a market name (e.g., 'R1 480m')."""
        match = re.search(r"\bR(\d{1,2})\b", name)
        return int(match.group(1)) if match else 0

    def _get_datetime_range(self, date_str: str):
        # Helper to create a datetime range for the Betfair API
        start_time = datetime.strptime(date_str, "%Y-%m-%d")
        end_time = start_time + timedelta(days=1)
        return start_time, end_time
