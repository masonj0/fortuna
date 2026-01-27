# python_service/adapters/fanduel_adapter.py

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy
from ..models import Race, Runner
from .base_adapter_v3 import BaseAdapterV3
from .utils.odds_validator import create_odds_data


class FanDuelAdapter(BaseAdapterV3):
    """
    Adapter for FanDuel's private API, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "FanDuel"
    BASE_URL = "https://sb-api.nj.sportsbook.fanduel.com/api/"

    def __init__(self, config=None, session=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        """Fetches the raw market data from the FanDuel API."""
        # Using a representative eventId as a placeholder for the discovery mechanism
        event_id = "38183.3"
        endpoint = f"markets?_ak=Fh2e68s832c41d4b&eventId={event_id}"
        response = await self.make_request("GET", endpoint)
        return response.json() if response else None

    def _parse_races(self, raw_data: Optional[Dict[str, Any]]) -> List[Race]:
        """Parses the raw API response into a list of Race objects."""
        if not raw_data or "marketGroups" not in raw_data:
            return []

        races = []
        for group in raw_data.get("marketGroups", []):
            if group.get("marketGroupName") == "Win":
                for market in group.get("markets", []):
                    try:
                        if race := self._parse_single_race(market):
                            races.append(race)
                    except Exception:
                        self.logger.error(
                            "Failed to parse a FanDuel market",
                            market_id=market.get("marketId"),
                            exc_info=True,
                        )
        return races

    def _parse_single_race(self, market: Dict[str, Any]) -> Optional[Race]:
        """Parses a single market from the API response into a Race object."""
        market_name = market.get("marketName", "")
        if not market_name.startswith("Race"):
            return None

        parts = market_name.split(" - ")
        if len(parts) < 2:
            return None

        race_number_str = parts[0].replace("Race ", "").strip()
        if not race_number_str.isdigit():
            return None
        race_number = int(race_number_str)

        track_name = parts[1]
        start_time = datetime.now(timezone.utc) + timedelta(hours=race_number)

        runners = []
        for runner_data in market.get("runners", []):
            try:
                runner_name = runner_data.get("runnerName")
                win_runner_odds = runner_data.get("winRunnerOdds", {})
                current_price = win_runner_odds.get("currentPrice")

                if not runner_name or not current_price:
                    continue

                numerator, denominator = map(int, current_price.split("/"))
                decimal_odds = Decimal(numerator) / Decimal(denominator) + 1

                name_parts = runner_name.split(".", 1)
                if len(name_parts) < 2:
                    continue

                program_number_str = name_parts[0].strip()
                horse_name = name_parts[1].strip()

                odds = {}
                if odds_data := create_odds_data(self.source_name, decimal_odds):
                    odds[self.source_name] = odds_data

                runners.append(
                    Runner(
                        name=horse_name,
                        number=(int(program_number_str) if program_number_str.isdigit() else 0),
                        odds=odds,
                    )
                )
            except (ValueError, ZeroDivisionError, IndexError, TypeError):
                continue

        if not runners:
            return None

        race_id = f"FD-{track_name.replace(' ', '')[:5].upper()}-{start_time.strftime('%Y%m%d')}-R{race_number}"

        return Race(
            id=race_id,
            venue=track_name,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )
