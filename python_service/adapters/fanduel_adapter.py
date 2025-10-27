# python_service/adapters/fanduel_adapter.py

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..models import OddsData, Race, Runner
from .base_v3 import BaseAdapterV3


class FanDuelAdapter(BaseAdapterV3):
    """
    Adapter for FanDuel's private API, migrated to BaseAdapterV3.
    """
    SOURCE_NAME = "FanDuel"
    BASE_URL = "https://sb-api.nj.sportsbook.fanduel.com/api/"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Any:
        """Fetches the raw market data from the FanDuel API."""
        # Note: FanDuel's API is not date-centric. Event discovery would be needed for a robust implementation.
        # This uses a hardcoded eventId as a placeholder.
        event_id = "38183.3"
        self.logger.info(f"Fetching races from FanDuel for event_id: {event_id}")
        endpoint = f"markets?_ak=Fh2e68s832c41d4b&eventId={event_id}"
        response = await self.make_request(self.http_client, "GET", endpoint)
        return response.json() if response else None

    def _parse_races(self, raw_data: Dict[str, Any]) -> List[Race]:
        """Parses the raw API response into a list of Race objects."""
        if not raw_data or "marketGroups" not in raw_data:
            self.logger.warning("FanDuel response missing 'marketGroups' key")
            return []

        races = []
        for group in raw_data["marketGroups"]:
            if group.get("marketGroupName") == "Win":
                for market in group.get("markets", []):
                    try:
                        if race := self._parse_single_race(market):
                            races.append(race)
                    except Exception:
                        self.logger.error("Failed to parse a FanDuel market", market=market, exc_info=True)
        return races

    def _parse_single_race(self, market: Dict[str, Any]) -> Optional[Race]:
        """Parses a single market from the API response into a Race object."""
        market_name = market.get("marketName", "")
        if not market_name.startswith("Race"):
            return None

        parts = market_name.split(" - ")
        if len(parts) < 2:
            self.logger.warning(f"Could not parse race and track from FanDuel market name: {market_name}")
            return None

        race_number_str = parts[0].replace("Race ", "")
        track_name = parts[1]

        # Placeholder for start_time - FanDuel's market API doesn't provide it directly
        start_time = datetime.now(timezone.utc) + timedelta(hours=int(race_number_str))

        runners = []
        for runner_data in market.get("runners", []):
            try:
                runner_name = runner_data.get("runnerName")
                win_odds = runner_data.get("winRunnerOdds", {}).get("currentPrice")
                if not runner_name or not win_odds:
                    continue

                numerator, denominator = map(int, win_odds.split("/"))
                decimal_odds = Decimal(numerator) / Decimal(denominator) + 1

                odds = OddsData(win=decimal_odds, source=self.source_name, last_updated=datetime.now(timezone.utc))
                program_number_str = runner_name.split(".")[0].strip()

                runners.append(Runner(
                    name=runner_name.split(".")[1].strip(),
                    number=int(program_number_str) if program_number_str.isdigit() else 0,
                    odds={self.source_name: odds},
                ))
            except (ValueError, ZeroDivisionError, IndexError):
                self.logger.warning("Could not parse FanDuel runner", runner_data=runner_data, exc_info=True)
                continue

        if not runners:
            return None

        race_id = f"FD-{track_name.replace(' ', '')[:5].upper()}-{start_time.strftime('%Y%m%d')}-R{race_number_str}"

        return Race(
            id=race_id,
            venue=track_name,
            race_number=int(race_number_str),
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )
