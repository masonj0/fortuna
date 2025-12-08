import pytest
import shutil
from pathlib import Path

CACHE_DIR = Path("python_service/cache")

@pytest.fixture
async def clear_cache():
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    yield
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
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
    # Add sensible defaults for engine/HTTP client initialization
    HTTP_POOL_CONNECTIONS: int = 100
    HTTP_MAX_KEEPALIVE: int = 20
    API_KEY: str = "test-api-key-123"
    MAX_CONCURRENT_REQUESTS: int = 50
    # Add dummy values for adapter tests
    GREYHOUND_API_URL: str = "http://test-greyhound-api.com"
    THE_RACING_API_KEY: str = "test-racing-api-key"

def get_test_settings() -> TestSettings:
    return TestSettings()

# --- 3. Event Loop (Function Scope) ---
# FIX: The explicit event_loop fixture is removed. pytest-asyncio will now manage the loop.
# This prevents a RuntimeError with the ThreadPoolExecutor during the app's lifespan startup.

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
