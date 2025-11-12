# tests/conftest.py
from contextlib import asynccontextmanager
from unittest.mock import Mock
from unittest.mock import patch

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python_service.api import app
from python_service.api import get_settings
from python_service.config import Settings
from python_service.engine import OddsEngine
from python_service.manual_override_manager import ManualOverrideManager


def get_test_settings():
    """
    Returns a comprehensive, test-specific Settings object that satisfies all
    adapter configuration requirements. This prevents AdapterConfigErrors during
    app startup in a test environment.
    """
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
    A TestClient instance for testing the FastAPI app.
    This fixture handles the setup and teardown of dependency overrides
    and a custom, synchronous lifespan for tests.
    """

    @asynccontextmanager
    async def test_lifespan(app_for_lifespan: FastAPI):
        """A synchronous, test-friendly version of the app's lifespan."""
        settings = get_test_settings()
        # No background thread needed for tests. Initialize directly.
        app_for_lifespan.state.engine = OddsEngine(config=settings)
        app_for_lifespan.state.manual_override_manager = ManualOverrideManager()
        yield
        # No shutdown tasks needed for test client

    # Temporarily replace the real lifespan with our test version
    original_lifespan = app.router.lifespan_context
    app.router.lifespan_context = test_lifespan

    # Override settings dependency
    original_get_settings = app.dependency_overrides.get(get_settings)
    app.dependency_overrides[get_settings] = get_test_settings

    # This patch is critical. It replaces the real Redis connection with a fake one.
    with patch(
        "redis.from_url", new_callable=lambda: fakeredis.aioredis.FakeRedis.from_url
    ), patch(
        "python_service.credentials_manager.SecureCredentialsManager.get_betfair_credentials",
        return_value=("test_user", "test_pass"),
    ):
        # Create a client that will run our test_lifespan on startup
        with TestClient(app) as test_client:
            yield test_client

    # Clean up overrides and restore the original lifespan
    app.router.lifespan_context = original_lifespan
    if original_get_settings:
        app.dependency_overrides[get_settings] = original_get_settings
    else:
        app.dependency_overrides.clear()


@pytest_asyncio.fixture
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
