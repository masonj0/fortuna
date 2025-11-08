# python_service/adapters/tab_adapter.py
from typing import Any
from typing import List

from ..models import Race
from .base_adapter_v3 import BaseAdapterV3


class TabAdapter(BaseAdapterV3):
    """
    Adapter for tab.com.au.
    This adapter is a non-functional stub and has not been implemented.
    """

    SOURCE_NAME = "TAB"
    BASE_URL = "https://www.tab.com.au"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config
        )

    async def _fetch_data(self, date: str) -> Any:
        """This is a stub and does not fetch any data."""
        self.logger.warning(
            f"{self.source_name} is a non-functional stub and has not been implemented. It will not fetch any data."
        )
        return None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """This is a stub and does not parse any data."""
        return []
