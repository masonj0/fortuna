# tests/test_api.py
from datetime import date
from datetime import datetime
from unittest.mock import AsyncMock
from unittest.mock import patch

import aiosqlite
import pytest

# --- Fixtures ---
from python_service.models import AggregatedResponse

# The client fixture is now correctly sourced from conftest.py,
# which handles the settings override globally.

# --- API Tests ---


@pytest.mark.asyncio
@patch("python_service.engine.OddsEngine.fetch_all_odds", new_callable=AsyncMock)
async def test_get_races_endpoint_success(mock_fetch_all_odds, client):
    """
    SPEC: The /api/races endpoint should return data with a valid API key.
    """
    # ARRANGE
    today = date.today()
    mock_response = AggregatedResponse(
        date=today,
        races=[],
            errors=[],
        sources=[],
        metadata={},
        # This was the missing field causing the validation error
        source_info=[],
    )
    mock_fetch_all_odds.return_value = mock_response.model_dump()
    from tests.conftest import get_test_settings
    settings = get_test_settings()
    headers = {"X-API-Key": settings.API_KEY}

    # ACT
    response = await client.get(f"/api/races?race_date={today.isoformat()}", headers=headers)

    # ASSERT
    assert response.status_code == 200
    mock_fetch_all_odds.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_tipsheet_endpoint_success(tmp_path, client):
    """
    SPEC: The /api/tipsheet endpoint should return a list of tipsheet races from the database.
    """
    db_path = tmp_path / "test.db"
    post_time = datetime.now()

    with patch("python_service.api.DB_PATH", db_path):
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                CREATE TABLE tipsheet (
                    race_id TEXT PRIMARY KEY,
                    track_name TEXT,
                    race_number INTEGER,
                    post_time TEXT,
                    score REAL,
                    factors TEXT
                )
            """
            )
            await db.execute(
                "INSERT INTO tipsheet VALUES (?, ?, ?, ?, ?, ?)",
                ("test_race_1", "Test Park", 1, post_time.isoformat(), 85.5, "{}"),
            )
            await db.commit()

        # ACT
        response = await client.get(f"/api/tipsheet?date={post_time.date().isoformat()}")

        # ASSERT
        assert response.status_code == 200
        response_data = response.json()
        assert len(response_data) == 1
        # The database returns snake_case, but the Pydantic model is camelCase
        assert response_data[0]["raceId"] == "test_race_1"
        assert response_data[0]["score"] == 85.5


@pytest.mark.asyncio
async def test_health_check_unauthenticated(client):
    """Ensures the /health endpoint is accessible without an API key."""
    response = await client.get("/health")
    assert response.status_code == 200
    json_response = response.json()
    assert json_response["status"] == "healthy"


@pytest.mark.asyncio
async def test_api_key_authentication_failure(client):
    """Ensures that endpoints are protected and fail with an invalid API key."""
    response = await client.get("/api/races/qualified/trifecta", headers={"X-API-KEY": "invalid_key"})
    assert response.status_code == 403
    assert "Invalid or missing API Key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_key_authentication_missing(client):
    """Ensures that endpoints are protected and fail with a missing API key."""
    response = await client.get("/api/races/qualified/trifecta")
    assert response.status_code == 403
    assert "Not authenticated" in response.json()["detail"]
