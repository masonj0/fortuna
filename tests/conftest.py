# tests/conftest.py
from unittest.mock import Mock
from unittest.mock import patch

import fakeredis.aioredis
import httpx
import pytest
from fastapi.testclient import TestClient

from python_service.api import app
from python_service.api import get_settings
from python_service.config import Settings


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
        GREYHOUND_API_URL="https://api.example.com/greyhound",
    )


@pytest.fixture(scope="function")
def client():
    """
    A TestClient instance for testing the FastAPI app.
    This fixture handles the setup and teardown of dependency overrides.
    """
    original_get_settings = app.dependency_overrides.get(get_settings)
    app.dependency_overrides[get_settings] = get_test_settings

    # This patch is critical. It replaces the real Redis connection with a fake,
    # in-memory one *before* the TestClient starts the FastAPI application.
    # This allows the app's `lifespan` startup event, which initializes the
    # cache_manager, to complete successfully without a live Redis server.
    with patch("redis.from_url", new_callable=lambda: fakeredis.aioredis.FakeRedis.from_url), \
         patch("python_service.credentials_manager.SecureCredentialsManager.get_betfair_credentials", return_value=("test_user", "test_pass")):
        with patch(
            "python_service.credentials_manager.keyring.get_password",
            side_effect=lambda s, u: f"test_{u}",
        ):
            # THE FIX: Directly instantiate the client. The context manager (`with`)
            # is no longer the recommended pattern and can cause issues.
            test_client = TestClient(app)
            yield test_client

    # Clean up the override
    if original_get_settings:
        app.dependency_overrides[get_settings] = original_get_settings
    else:
        app.dependency_overrides.clear()


@pytest.fixture()
async def clear_cache():
    """A fixture to ensure the cache is cleared before a test."""
    from python_service.cache_manager import cache_manager
    if cache_manager.is_configured and cache_manager.redis_client:
        await cache_manager.redis_client.flushdb()
    cache_manager.memory_cache.clear()


@pytest.fixture
def mock_httpx_client():
    """Mocks the httpx.AsyncClient for testing adapters."""
    return Mock(spec=httpx.AsyncClient)
