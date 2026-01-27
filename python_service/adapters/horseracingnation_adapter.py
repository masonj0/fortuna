from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy
# python_service/adapters/horseracingnation_adapter.py
from typing import Any
from typing import List

from ..models import Race
from .base_adapter_v3 import BaseAdapterV3


class HorseRacingNationAdapter(BaseAdapterV3):
    """
    Adapter for horseracingnation.com.
    This adapter is a non-functional stub and has not been implemented.
    """

    SOURCE_NAME = "HorseRacingNation"
    BASE_URL = "https://www.horseracingnation.com"

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Any:
        """This is a stub and does not fetch any data."""
        self.logger.warning(
            f"{self.source_name} is a non-functional stub and has not been implemented. It will not fetch any data."
        )
        return None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """This is a stub and does not parse any data."""
        return []
