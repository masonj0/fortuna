import pytest
import pytest_asyncio
import asyncio
from httpx import AsyncClient
from asgi_lifespan import LifespanManager

# FIX: Handle fakeredis import for newer versions
try:
    from fakeredis import FakeAsyncRedis
except ImportError:
    # Fallback or mock if fakeredis is missing (prevents crash)
    FakeAsyncRedis = None

@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
async def redis_client():
    """Mock Redis client."""
    if FakeAsyncRedis:
        server = FakeAsyncRedis()
        yield server
        await server.close()
    else:
        pytest.skip("fakeredis not installed")
