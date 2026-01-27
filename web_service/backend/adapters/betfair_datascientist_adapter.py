# python_service/adapters/betfair_datascientist_adapter.py

from datetime import datetime
from io import StringIO
from typing import List, Optional

import pandas as pd

from ..models import Race, Runner
from ..utils.text import normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3
from .utils.odds_validator import create_odds_data
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy


class BetfairDataScientistAdapter(BaseAdapterV3):
    """
    Adapter for the Betfair Data Scientist CSV models, migrated to BaseAdapterV3.
    """

    ADAPTER_NAME = "BetfairDataScientist"

    def __init__(self, model_name: str, url: str, config=None):
        source_name = f"{self.ADAPTER_NAME}_{model_name}"
        super().__init__(source_name=source_name, base_url=url, config=config)
        self.model_name = model_name

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    async def _fetch_data(self, date: str) -> Optional[StringIO]:
        """Fetches the raw CSV data from the Betfair Data Scientist model endpoint."""
        endpoint = f"?date={date}&presenter=RatingsPresenter&csv=true"
        self.logger.info(f"Fetching data from {self.base_url}{endpoint}")
        response = await self.make_request("GET", endpoint)
        return StringIO(response.text) if response and response.text else None

    def _parse_races(self, raw_data: Optional[StringIO]) -> List[Race]:
        """Parses the raw CSV data into a list of Race objects."""
        if not raw_data:
            return []
        try:
            df = pd.read_csv(raw_data)
            if df.empty:
                self.logger.warning("Received empty CSV from Betfair Data Scientist.")
                return []

            df = df.rename(
                columns={
                    "meetings.races.bfExchangeMarketId": "market_id",
                    "meetings.races.runners.bfExchangeSelectionId": "selection_id",
                    "meetings.races.runners.ratedPrice": "rated_price",
                    "meetings.races.raceName": "race_name",
                    "meetings.name": "meeting_name",
                    "meetings.races.raceNumber": "race_number",
                    "meetings.races.runners.runnerName": "runner_name",
                    "meetings.races.runners.clothNumber": "saddle_cloth",
                }
            )
            races: List[Race] = []
            for market_id, group in df.groupby("market_id"):
                race_info = group.iloc[0]
                runners = []
                for _, row in group.iterrows():
                    rated_price = row.get("rated_price")
                    odds_data = {}
                    if pd.notna(rated_price):
                        if odds_val := create_odds_data(self.source_name, float(rated_price)):
                            odds_data[self.source_name] = odds_val

                    runners.append(
                        Runner(
                            name=str(row.get("runner_name", "Unknown")),
                            number=int(row.get("saddle_cloth", 0)),
                            odds=odds_data,
                        )
                    )

                race = Race(
                    id=str(market_id),
                    venue=normalize_venue_name(str(race_info.get("meeting_name", ""))),
                    race_number=int(race_info.get("race_number", 0)),
                    start_time=datetime.now(),  # Placeholder, not provided in source
                    runners=runners,
                    source=self.source_name,
                )
                races.append(race)
            self.logger.info(f"Normalized {len(races)} races from {self.model_name}.")
            return races
        except (pd.errors.ParserError, KeyError) as e:
            self.logger.error(
                "Failed to parse Betfair Data Scientist CSV.",
                exc_info=True,
                error=str(e),
            )
            return []
