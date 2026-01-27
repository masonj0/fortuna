# python_service/adapters/stubs/racingtv_adapter.py
from ..base_stub_adapter import BaseStubAdapter


class RacingTVAdapter(BaseStubAdapter):
    """Stub adapter for racingtv.com."""

    SOURCE_NAME = "RacingTV"
    BASE_URL = "https://www.racingtv.com"
