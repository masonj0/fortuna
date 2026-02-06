# python_service/adapters/stubs/template_adapter.py
"""Template for creating new adapters."""

from typing import Any, List

from ...core.smart_fetcher import BrowserEngine, FetchStrategy
from ...models import Race
from ..base_adapter_v3 import BaseAdapterV3


class TemplateAdapter(BaseAdapterV3):
    """
    A template for creating new adapters based on BaseAdapterV3.

    To create a new adapter:
    1. Copy this file and rename it
    2. Update SOURCE_NAME and BASE_URL
    3. Implement _configure_fetch_strategy() based on site requirements
    4. Implement _fetch_data() to retrieve raw data
    5. Implement _parse_races() to convert raw data to Race objects
    """

    SOURCE_NAME = "[IMPLEMENT ME] Example Source"
    BASE_URL = "https://api.example.com"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config
        )
        # Example: self.api_key = config.EXAMPLE_API_KEY

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """
        Configure the fetch strategy based on site requirements.

        Options:
        - BrowserEngine.HTTPX: Simple HTTP (fastest, use for APIs)
        - BrowserEngine.PLAYWRIGHT: Full browser (for JS-heavy sites)

        Additional options:
        - enable_js: Whether to execute JavaScript
        - stealth_mode: Level of anti-detection measures
        - block_resources: Block images/fonts for performance
        """
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    async def _fetch_data(self, date: str) -> Any:
        """
        Fetch raw data for the given date.

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            Raw data (dict, list, string, etc.) or None on failure
        """
        self.logger.warning(
            f"{self.source_name} is a template - implement _fetch_data()"
        )
        return None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """
        Parse raw data into Race objects.

        Args:
            raw_data: Data returned from _fetch_data()

        Returns:
            List of Race objects
        """
        return []
