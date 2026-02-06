# python_service/adapters/base_stub_adapter.py
"""Base class for non-functional stub adapters."""

from abc import ABC
from typing import Any, List

from ..core.smart_fetcher import BrowserEngine, FetchStrategy
from ..models import Race
from .base_adapter_v3 import BaseAdapterV3


class BaseStubAdapter(BaseAdapterV3, ABC):
    """
    Base class for adapters that are not yet implemented.

    Subclasses only need to define SOURCE_NAME and BASE_URL.
    """

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config
        )

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    async def _fetch_data(self, date: str) -> Any:
        """Stub implementation - logs warning and returns None."""
        self.logger.warning(
            "Adapter is a non-functional stub",
            adapter=self.source_name,
            message="This adapter has not been implemented and will not fetch any data."
        )
        return None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Stub implementation - returns empty list."""
        return []
