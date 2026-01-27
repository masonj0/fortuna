# python_service/adapters/stubs/punters_adapter.py
from ..base_stub_adapter import BaseStubAdapter


class PuntersAdapter(BaseStubAdapter):
    """Stub adapter for punters.com.au."""

    SOURCE_NAME = "Punters"
    BASE_URL = "https://www.punters.com.au"
