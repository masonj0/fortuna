# python_service/adapters/stubs/nyrabets_adapter.py
from ..base_stub_adapter import BaseStubAdapter


class NYRABetsAdapter(BaseStubAdapter):
    """Stub adapter for nyrabets.com."""

    SOURCE_NAME = "NYRABets"
    BASE_URL = "https://nyrabets.com"
