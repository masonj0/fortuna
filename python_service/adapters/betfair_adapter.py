# python_service/adapters/betfair_adapter.py
from datetime import datetime
from typing import List

import httpx

from ..core.exceptions import AdapterAuthError, AdapterParsingError
from ..models import Race, Runner
from .base import BaseAdapter
from .betfair_auth_mixin import BetfairAuthMixin


class BetfairAdapter(BetfairAuthMixin, BaseAdapter):
    """Adapter for fetching horse racing data from the Betfair Exchange API."""

    def __init__(self, config: dict):
        super().__init__(source_name="BetfairExchange", base_url="https://api.betfair.com/exchange/betting/rest/v1.0/", config=config)

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> List[Race]:
        """Fetches the raw market catalogue for a given date and parses it."""
        await self._authenticate(http_client)
        if not self.session_token:
            raise AdapterAuthError(self.source_name, "Authentication failed, cannot fetch data.")

        start_time, end_time = self._get_datetime_range(date)

        response = await self.make_request(
            http_client=http_client,
            method="post",
            url="listMarketCatalogue/",
            json={
                "filter": {
                    "eventTypeIds": ["7"],  # Horse Racing
                    "marketCountries": ["GB", "IE", "AU", "US", "FR", "ZA"],
                    "marketTypeCodes": ["WIN"],
                    "marketStartTime": {"from": start_time.isoformat(), "to": end_time.isoformat()}
                },
                "maxResults": 1000,
                "marketProjection": ["EVENT", "RUNNER_DESCRIPTION"]
            }
        )
        raw_data = response.json()

        if not raw_data:
            return []

        races = []
        for market in raw_data:
            try:
                races.append(self._parse_race(market))
            except (KeyError, TypeError) as e:
                self.logger.warning("Failed to parse a Betfair market.", exc_info=True, market=market)
                raise AdapterParsingError(self.source_name, f"Failed to parse market: {market.get('marketId')}") from e
        return races

    def _parse_race(self, market: dict) -> Race:
        """Parses a single market from the Betfair API into a Race object."""
        market_id = market['marketId']
        event = market['event']
        start_time = datetime.fromisoformat(market['marketStartTime'].replace('Z', '+00:00'))

        runners = [
            Runner(
                number=runner.get('sortPriority', i + 1),
                name=runner['runnerName'],
                scratched=runner['status'] != 'ACTIVE',
                selection_id=runner['selectionId']
            )
            for i, runner in enumerate(market.get('runners', []))
        ]

        return Race(
            id=f"bf_{market_id}",
            venue=event.get('venue', 'Unknown Venue'),
            race_number=self._extract_race_number(market.get('marketName', '')),
            start_time=start_time,
            runners=runners,
            source=self.SOURCE_NAME
        )

    def _extract_race_number(self, name: str) -> int:
        """Extracts the race number from a market name (e.g., 'R1 1m Mdn Stks')."""
        import re
        match = re.search(r'\bR(\d{1,2})\b', name)
        return int(match.group(1)) if match else 0