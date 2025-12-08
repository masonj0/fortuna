import sys
import os
import shutil
import pytest
import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from decimal import Decimal
from datetime import datetime

# =============================================================================
# 1. SYSTEM PATH INJECTION (The 'ModuleNotFoundError' Killer)
# =============================================================================
# This ensures that 'python_service' and 'web_service' are importable
# regardless of where pytest is run from.
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# =============================================================================
# 2. MOCK SETTINGS (The 'AttributeError' Killer)
# =============================================================================
class MockSettings:
    """Safe settings that don't require .env files or secrets."""
    API_KEY = "test-override-key-123"
    REDIS_URL = "redis://localhost:6379/0"
    CACHE_ENABLED = True
    HTTP_POOL_CONNECTIONS = 100
    HTTP_MAX_KEEPALIVE = 20
    MAX_CONCURRENT_REQUESTS = 50
    # Add any other required config fields here

@pytest.fixture(scope="session")
def test_settings():
    return MockSettings()

# =============================================================================
# 3. GLOBAL MOCKS (The 'RuntimeError' & 'Connection Refused' Killer)
# =============================================================================
@pytest.fixture(scope="session", autouse=True)
def mock_dangerous_dependencies():
    """
    Automatically mocks out dangerous background tasks (Redis, DB connections)
    that crash the test runner when the event loop closes.
    """
    # 1. Kill the heavy background initialization task
    p1 = patch("python_service.api._initialize_heavy_resources_sync")
    # 2. Kill the database session generator
    p2 = patch("python_service.db.init.initialize_database")

    mock_init = p1.start()
    mock_db = p2.start()

    yield

    p1.stop()
    p2.stop()

# =============================================================================
# 4. ASYNCIO EVENT LOOP
# =============================================================================
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

# =============================================================================
# 5. FASTAPI APP & CLIENT
# =============================================================================
@pytest.fixture
async def app(mock_dangerous_dependencies, test_settings):
    from asgi_lifespan import LifespanManager
    from python_service.api import app as fastapi_app
    from python_service.engine import OddsEngine

    # Attach a mock engine to the app state to prevent startup hangs
    fastapi_app.state.engine = OddsEngine(config=test_settings)

    # Increase timeout to 30s to prevent slow CI runners from failing
    async with LifespanManager(fastapi_app, startup_timeout=30) as manager:
        yield manager

@pytest.fixture
async def client(app):
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        ac.app = app
        yield ac

# =============================================================================
# 6. CACHE FIXTURE (The 'fixture not found' Killer)
# =============================================================================
CACHE_DIR = Path("python_service/cache")

@pytest.fixture
async def clear_cache():
    """Ensures a clean slate for file-based caches."""
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
    yield
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)

# =============================================================================
# 7. DATA HELPERS (The Logic Validator)
# =============================================================================
def create_mock_race(source, venue, race_number, start_time, runners_data):
    """
    Creates a standardized race object compatible with the OddsEngine.
    Handles the Pydantic model structure required for aggregation.
    """
    # We return a Dict that mimics the Pydantic model structure.
    # This is often safer for tests than instantiating complex models directly.

    runners = []
    for r in runners_data:
        # Construct the nested odds dictionary: { 'Source': { 'win': Decimal(...) } }
        odds_struct = {source: {'win': Decimal(str(r.get('odds', '0.0')))}}

        runners.append({
            "number": r['number'],
            "name": r['name'],
            "odds": odds_struct
        })

    return {
        "id": f"{venue}_{race_number}_{start_time}",
        "venue": venue,
        "race_number": race_number,
        "start_time": start_time,
        "source": source,  # Critical for deduplication logic
        "runners": runners
    }

# Helper to inject settings into tests if needed
def get_test_settings():
    return MockSettings()