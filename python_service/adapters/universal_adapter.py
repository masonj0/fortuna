# python_service/adapters/universal_adapter.py
import json
from typing import Any, List

from selectolax.parser import HTMLParser

from ..models import Race
from .base_adapter_v3 import BaseAdapterV3
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy


class UniversalAdapter(BaseAdapterV3):
    """
    An adapter that executes logic from a declarative JSON definition file.
    NOTE: This is a simplified proof-of-concept implementation.
    Standardized on selectolax for performance.
    """

    def __init__(self, config, definition_path: str):
        with open(definition_path, "r") as f:
            self.definition = json.load(f)

        super().__init__(
            source_name=self.definition["adapter_name"],
            base_url=self.definition["base_url"],
            config=config,
        )

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    async def _fetch_data(self, date: str) -> Any:
        """Executes the fetch steps defined in the JSON definition."""
        self.logger.info(f"Executing Universal Adapter PoC for {self.source_name}")
        response = await self.make_request("GET", self.definition["start_url"])
        if not response:
            return None

        parser = HTMLParser(response.text)
        # Assuming the first step is a simple CSS selector for track links
        track_links = [self.base_url + a.attributes["href"] for a in parser.css(self.definition["steps"][0]["selector"]) if a.attributes.get("href")]

        # In a full implementation, we would fetch and return each track page's content.
        # For this PoC, we are not fetching the individual track links.
        self.logger.warning("UniversalAdapter is a proof-of-concept and does not fully fetch all data.")
        return track_links

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """This is a proof-of-concept and does not parse any data."""
        return []
