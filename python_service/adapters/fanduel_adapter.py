# python_service/adapters/fanduel_adapter.py

from datetime import datetime
from datetime import timedelta
from datetime import timezone
from decimal import Decimal
from typing import Any
from typing import Dict
from typing import List
from typing import Optional

import httpx
import structlog

from ..core.exceptions import AdapterParsingError
from ..models import OddsData
from ..models import Race
from ..models import Runner
from .base import BaseAdapter

log = structlog.get_logger()


class FanDuelAdapter(BaseAdapter):
    """
    Adapter for fetching horse racing odds from FanDuel's private API.
    This adapter now follows the modern fetch/parse pattern.
    """

    def __init__(self, config):
        super().__init__(source_name="FanDuel", base_url="https://sb-api.nj.sportsbook.fanduel.com/api/", config=config)

    async def _fetch_data(self, http_client: httpx.AsyncClient, date: str) -> Any:
        """Fetches the raw market data from the FanDuel API."""
        event_id = "38183.3"  # Placeholder for event discovery
        self.logger.info("Fetching races from FanDuel", event_id=event_id)
        endpoint = f"markets?_ak=Fh2e68s832c41d4b&eventId={event_id}"
        response = await self.make_request(http_client, "GET", endpoint)
        return response.json()

    def _parse_races(self, raw_data: Dict[str, Any]) -> List[Race]:
        """Parses the raw API response into a list of Race objects."""
        if "marketGroups" not in raw_data:
            self.logger.warning("FanDuel response missing 'marketGroups' key")
            return []

        races = []
        for group in raw_data["marketGroups"]:
            if group.get("marketGroupName") == "Win":
                for market in group.get("markets", []):
                    try:
                        if race := self._parse_single_race(market):
                            races.append(race)
                    except AdapterParsingError as e:
                        self.logger.error("Failed to parse a FanDuel market", market=market, error=str(e))
        return races

    def _parse_single_race(self, market: Dict[str, Any]) -> Optional[Race]:
        market_name = market.get("marketName", "")
        if not market_name.startswith("Race"):
            return None

        parts = market_name.split(" - ")
        if len(parts) < 2:
            raise AdapterParsingError(
                self.source_name,
                f"Could not parse race and track from market name: {market_name}",
            )

        race_number_str = parts[0].replace("Race ", "")
        track_name = parts[1]

        # Placeholder for start_time - FanDuel's market API doesn't provide it directly
        start_time = datetime.now(timezone.utc) + timedelta(hours=int(race_number_str))

        runners = []
        for runner_data in market.get("runners", []):
            runner_name = runner_data.get("runnerName")
            win_odds = runner_data.get("winRunnerOdds", {}).get("currentPrice")
            if not runner_name or not win_odds:
                continue

            try:
                numerator, denominator = map(int, win_odds.split("/"))
                decimal_odds = Decimal(numerator) / Decimal(denominator) + 1
            except (ValueError, ZeroDivisionError):
                log.warning("Could not parse FanDuel odds", odds_str=win_odds, runner=runner_name)
                continue

            odds = OddsData(win=decimal_odds, source=self.source_name, last_updated=datetime.now(timezone.utc))

            program_number_str = runner_name.split(".")[0].strip()

            runners.append(Runner(
                name=runner_name.split(".")[1].strip(),
                number=int(program_number_str) if program_number_str.isdigit() else None,
                odds={self.source_name: odds},
            ))

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
