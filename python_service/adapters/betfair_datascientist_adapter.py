# python_service/adapters/betfair_datascientist_adapter.py

from datetime import datetime
from io import StringIO
from typing import List

import httpx
import pandas as pd
import structlog

from ..core.exceptions import AdapterParsingError
from ..models import Race, Runner
from ..utils.text import normalize_course_name
from .base import BaseAdapter


class BetfairDataScientistAdapter(BaseAdapter):
    """
    Adapter for the Betfair Data Scientist CSV models.
    This adapter is instantiated dynamically by the engine for each configured model.
    """
    ADAPTER_NAME = "BetfairDataScientist"

    def __init__(self, model_name: str, url: str, config=None):
        source_name = f"{self.ADAPTER_NAME}_{model_name}"
        super().__init__(source_name=source_name, base_url=url, config=config)
        self.model_name = model_name

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> List[Race]:
        """Fetches and parses CSV data from the Betfair Data Scientist model endpoint."""
        endpoint = self._build_endpoint(date)
        self.logger.info(f"Fetching data from {self.base_url}{endpoint}")

        response = await self.make_request(http_client, "GET", endpoint)

        try:
            raw_data = StringIO(response.text)
            df = pd.read_csv(raw_data)
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
            races = []
            for market_id, group in df.groupby("market_id"):
                race_info = group.iloc[0]
                runners = [
                    Runner(
                        name=str(row.get("runner_name")),
                        number=int(row.get("saddle_cloth", 0)),
                        odds=float(row.get("rated_price", 0.0)),
                    )
                    for _, row in group.iterrows()
                ]
                race = Race(
                    id=str(market_id),
                    venue=normalize_course_name(str(race_info.get("meeting_name", ""))),
                    race_number=int(race_info.get("race_number", 0)),
                    # Note: The CSV does not provide a start time, using current time as a placeholder.
                    start_time=datetime.now(),
                    runners=runners,
                    source=self.source_name,
                )
                races.append(race)
            self.logger.info(f"Normalized {len(races)} races from {self.model_name}.")
            return races
        except (pd.errors.ParserError, KeyError) as e:
            self.logger.error("Failed to parse Betfair Data Scientist CSV.", error=str(e))
            raise AdapterParsingError(self.source_name, "Failed to parse CSV response.") from e

    def _build_endpoint(self, date: str) -> str:
        """Constructs the query parameters for the CSV endpoint."""
        return f"?date={date}&presenter=RatingsPresenter&csv=true"
