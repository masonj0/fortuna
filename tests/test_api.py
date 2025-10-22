# tests/test_api.py
import pytest
import aiosqlite
from unittest.mock import patch, AsyncMock
from datetime import datetime, date
from decimal import Decimal

from python_service.models import Race, Runner, OddsData, TipsheetRace, AggregatedResponse
from python_service.api import app, get_settings
from python_service.config import Settings

# --- Test Configuration ---

def get_test_settings():
    """Provides a mock settings object with all required API keys for testing."""
    return Settings(
        API_KEY="test_api_key",
        THE_RACING_API_KEY="test_racing_api_key",
        BETFAIR_APP_KEY="test_betfair_key",
        BETFAIR_USERNAME="test_user",
        BETFAIR_PASSWORD="test_password",
        TVG_API_KEY="test_tvg_key",
    )

app.dependency_overrides[get_settings] = get_test_settings


# --- Fixtures ---

from fastapi.testclient import TestClient

@pytest.fixture
def client():
    """Provides a TestClient for the FastAPI app, now with overridden settings."""
    with TestClient(app) as c:
        yield c

# --- API Tests ---

@pytest.mark.asyncio
@patch('python_service.engine.FortunaEngine.get_races', new_callable=AsyncMock)
async def test_get_races_endpoint_success(mock_get_races, client):
    """
    SPEC: The /api/races endpoint should return data with a valid API key.
    """
    # ARRANGE
    today = date.today()
    mock_response = AggregatedResponse(
        date=today,
        races=[],
        sources=[],
        metadata={},
        # This was the missing field causing the validation error
        source_info=[]
    )
    mock_get_races.return_value = mock_response.model_dump()
    headers = {"X-API-Key": "test_api_key"}

    # ACT
    response = client.get(f"/api/races?race_date={today.isoformat()}", headers=headers)

    # ASSERT
    assert response.status_code == 200
    mock_get_races.assert_awaited_once()

@pytest.mark.asyncio
async def test_get_tipsheet_endpoint_success(tmp_path, client):
    """
    SPEC: The /api/tipsheet endpoint should return a list of tipsheet races from the database.
    """
    db_path = tmp_path / "test.db"
    post_time = datetime.now()

    with patch('python_service.api.DB_PATH', db_path):
        async with aiosqlite.connect(db_path) as db:
            await db.execute("""
                CREATE TABLE tipsheet (
                    race_id TEXT PRIMARY KEY,
                    track_name TEXT,
                    race_number INTEGER,
                    post_time TEXT,
                    score REAL,
                    factors TEXT
                )
            """)
            await db.execute(
                "INSERT INTO tipsheet VALUES (?, ?, ?, ?, ?, ?)",
                ("test_race_1", "Test Park", 1, post_time.isoformat(), 85.5, "{}")
            )
            await db.commit()

        # ACT
        response = client.get(f"/api/tipsheet?date={post_time.date().isoformat()}")

        # ASSERT
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data) == 1
        # The database returns snake_case, but the Pydantic model is camelCase
        assert response_data[0]["raceId"] == "test_race_1"
        assert response_data[0]["score"] == 85.5

def test_health_check_unauthenticated(client):
    """Ensures the /health endpoint is accessible without an API key."""
    response = client.get("/health")
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "ok"
    assert "timestamp" in json_response

def test_api_key_authentication_failure(client):
    """Ensures that endpoints are protected and fail with an invalid API key."""
    response = client.get("/api/races/qualified/trifecta", headers={"X-API-KEY": "invalid_key"})
    assert response.status_code == 403
    assert "Invalid or missing API Key" in response.json()["detail"]


def test_api_key_authentication_missing(client):
    """Ensures that endpoints are protected and fail with a missing API key."""
    response = client.get("/api/races/qualified/trifecta")
    assert response.status_code == 403
    assert "Not authenticated" in response.json()["detail"]
