# tests/conftest.py
import pytest
from unittest.mock import patch, Mock
from fastapi.testclient import TestClient
import httpx
import os

from python_service.config import Settings
from python_service.api import app

@pytest.fixture(scope="session", autouse=True)
def override_settings():
    """
    This fixture is automatically used for the entire test session.
    It patches the `get_settings` function to return a test-specific,
    fully-populated Settings object. This prevents AdapterConfigErrors
    during app startup and ensures tests run in a controlled environment.
    """
    def get_test_settings():
        return Settings(
            API_KEY="test_api_key",
            THE_RACING_API_KEY="test_racing_api_key",
            BETFAIR_APP_KEY="test_betfair_key",
            BETFAIR_USERNAME="test_user",
            BETFAIR_PASSWORD="test_password",
            TVG_API_KEY="test_tvg_key",
            RACING_AND_SPORTS_TOKEN="test_token",
            GREYHOUND_API_URL="https://api.example.com" # Added for GreyhoundAdapter
        )

    # The engine gets its settings from the API module, so we only need to patch it there.
    with patch("python_service.api.get_settings", new=get_test_settings):
        yield


@pytest.fixture(scope="module")
def client():
    """A TestClient instance for testing the FastAPI app."""
    # The override_settings fixture will have already patched the settings
    with TestClient(app) as c:
        yield c

@pytest.fixture
def mock_httpx_client():
    """Mocks the httpx.AsyncClient for testing adapters."""
    return Mock(spec=httpx.AsyncClient)
