import pytest
import asyncio
import os
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from asgi_lifespan import LifespanManager

# --- 1. Redis Mocking ---
try:
    from fakeredis import FakeAsyncRedis
except ImportError:
    FakeAsyncRedis = None

# --- 2. Settings Mock ---
class TestSettings:
    redis_url: str = "redis://localhost:6379"
    database_url: str = "sqlite+aiosqlite:///:memory:"
    testing: bool = True

def get_test_settings() -> TestSettings:
    return TestSettings()

# --- 3. Event Loop (Function Scope) ---
# FIX: Changed scope to 'function' to match pytest-asyncio defaults and prevent shutdown errors
@pytest.fixture(scope="function")
def event_loop() -> Generator:
    """Create an instance of the default event loop for each test case."""
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

# --- 5. FastAPI App Fixture ---
@pytest.fixture
async def app():
    """Locate and yield the FastAPI application with lifespan management."""
    try:
        from python_service.main import app as fastapi_app
    except ImportError:
        try:
            from web_service.backend.main import app as fastapi_app
        except ImportError:
            pytest.skip("Could not import FastAPI app")

    async with LifespanManager(fastapi_app):
        yield fastapi_app

# --- 6. Async HTTP Client ---
@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
