from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy
# python_service/adapters/template_adapter.py
from typing import Any
from typing import List

from ..models import Race
from .base_adapter_v3 import BaseAdapterV3


class TemplateAdapter(BaseAdapterV3):
    """
    A template for creating new adapters, based on the BaseAdapterV3 pattern.
    This adapter is a non-functional stub.
    """

    SOURCE_NAME = "[IMPLEMENT ME] Example Source"
    BASE_URL = "https://api.example.com"

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)
        # self.api_key = config.EXAMPLE_API_KEY # Uncomment if needed

    async def _fetch_data(self, date: str) -> Any:
        """This is a stub and does not fetch any data."""
        self.logger.warning(
            f"{self.source_name} is a non-functional stub and has not been implemented. It will not fetch any data."
        )
        return None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """This is a stub and does not parse any data."""
        return []
