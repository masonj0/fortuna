# tests/conftest.py
import pytest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
import httpx

from python_service.config import Settings
from python_service.api import app, get_settings

def get_test_settings():
    """
    Returns a comprehensive, test-specific Settings object that satisfies all
    adapter configuration requirements. This prevents AdapterConfigErrors during
    app startup in a test environment.
    """
    return Settings(
        API_KEY="a_secure_test_api_key_that_is_long_enough",
        # Required by TheRacingApiAdapter
        THE_RACING_API_KEY="test_racing_api_key",
        # Required by Betfair adapters
        BETFAIR_APP_KEY="test_betfair_key",
        # Required by TVGAdapter
        TVG_API_KEY="test_tvg_key",
        # Required by RacingAndSports adapters
        RACING_AND_SPORTS_TOKEN="test_ras_token",
        # Required by GreyhoundAdapter
        GREYHOUND_API_URL="https://api.example.com/greyhound"
    )

@pytest.fixture(scope="module")
def client():
    """
    A TestClient instance for testing the FastAPI app.
    This fixture handles the setup and teardown of dependency overrides.
    """
    app.dependency_overrides[get_settings] = get_test_settings
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_httpx_client():
    """Mocks the httpx.AsyncClient for testing adapters."""
    return Mock(spec=httpx.AsyncClient)
