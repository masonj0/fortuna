# tests/conftest.py
from unittest.mock import Mock
from unittest.mock import patch

import fakeredis.aioredis
import httpx
import pytest
from fastapi.testclient import TestClient

from python_service.api import create_app
from python_service.config import Settings


def get_test_settings():
    """Returns a test-specific Settings object."""
    return Settings(
        API_KEY="a_secure_test_api_key_that_is_long_enough",
        THE_RACING_API_KEY="test_racing_api_key",
        BETFAIR_APP_KEY="test_betfair_key",
        TVG_API_KEY="test_tvg_key",
        RACING_AND_SPORTS_TOKEN="test_ras_token",
        GREYHOUND_API_URL="https://api.example.com/greyhound",
    )


@pytest.fixture(scope="function")
def client():
    """
    A robust TestClient fixture that uses the application factory pattern.
    This creates a clean, isolated FastAPI app for each test, configured
    with specific test settings, ensuring reliable and predictable test runs.
    """
    test_settings = get_test_settings()
    app = create_app(settings=test_settings)

    with patch("redis.from_url", new_callable=lambda: fakeredis.aioredis.FakeRedis.from_url), \
         patch("python_service.credentials_manager.SecureCredentialsManager.get_betfair_credentials", return_value=("test_user", "test_pass")):
        with TestClient(app) as test_client:
            yield test_client


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
