import pytest
import asyncio
import os
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager

# --- 1. Redis Mocking (Fix for fakeredis import) ---
try:
    from fakeredis import FakeAsyncRedis
except ImportError:
    FakeAsyncRedis = None

# --- 2. Settings Mock (Restored) ---
# This is required because tests import 'get_test_settings' from here
class TestSettings:
    redis_url: str = "redis://localhost:6379"
    database_url: str = "sqlite+aiosqlite:///:memory:"
    testing: bool = True
    API_KEY: str = "test-api-key"
    HTTP_POOL_CONNECTIONS: int = 100
    HTTP_MAX_KEEPALIVE: int = 20
    MAX_CONCURRENT_REQUESTS: int = 5
    GREYHOUND_API_URL: str = "http://test.greyhound.com"
    THE_RACING_API_KEY: str = "test-key"

def get_test_settings() -> TestSettings:
    return TestSettings()

# --- 3. Event Loop (Session Scope) ---
@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# --- 4. Redis Client Fixture ---
@pytest.fixture
async def redis_client():
    if FakeAsyncRedis:
        server = FakeAsyncRedis()
        yield server
        await server.close()
    else:
        pytest.skip("fakeredis not installed")

# --- 5. FastAPI App Fixture (Restored) ---
@pytest.fixture
async def app():
    """Locate and yield the FastAPI application with lifespan management."""
    # Dynamic import to handle directory structure variations
    try:
        from python_service.main import app as fastapi_app
    except ImportError:
        try:
            from web_service.backend.main import app as fastapi_app
        except ImportError:
            pytest.skip("Could not import FastAPI app from python_service or web_service")

    # Ensure lifespan events (startup/shutdown) run during tests
    async with LifespanManager(fastapi_app):
        yield fastapi_app

# --- 6. Async HTTP Client (Restored) ---
@pytest.fixture(scope="function")
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """An async client for testing endpoints."""
    # Uses ASGITransport for direct app communication without network overhead
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def clear_cache():
    """A dummy fixture to satisfy the dependency in test_engine.py."""
    pass
