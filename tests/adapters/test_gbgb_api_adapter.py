# tests/adapters/test_gbgb_api_adapter.py

import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

from tests.conftest import get_test_settings
from python_service.adapters.gbgb_api_adapter import GbgbApiAdapter

@pytest.fixture
def gbgb_adapter():
    """Returns a GbgbApiAdapter instance for testing."""
    return GbgbApiAdapter(config=get_test_settings())

@pytest.mark.asyncio
async def test_get_gbgb_races_successfully(gbgb_adapter):
    """
    SPEC: The GbgbApiAdapter should correctly parse a standard API response,
    creating Race and Runner objects with the correct data, including fractional odds.
    """
    # ARRANGE
    mock_date = date.today().strftime('%Y-%m-%d')
    mock_api_response = [
        {
            "trackName": "Towcester",
            "races": [
                {
                    "raceId": 12345,
                    "raceNumber": 1,
                    "raceTime": "2025-10-09T18:00:00Z",
                    "raceTitle": "The October Sprint",
                    "raceDistance": 500,
                    "traps": [
                        {"trapNumber": 1, "dogName": "Rapid Rover", "sp": "5/2"},
                        {"trapNumber": 2, "dogName": "Speedy Sue", "sp": "EVS"},
                        {"trapNumber": 3, "dogName": "Lazy Larry", "sp": "10/1"},
                    ],
                }
            ],
        }
    ]
    gbgb_adapter._fetch_data = AsyncMock(return_value=mock_api_response)

    # ACT
    races = [race async for race in gbgb_adapter.get_races(mock_date)]

    # ASSERT
    assert len(races) == 1
    race = races[0]
    assert race.venue == "Towcester"
    assert race.race_number == 1
    assert race.race_name == "The October Sprint"
    assert race.distance == "500m"
    assert len(race.runners) == 3

    runner1 = next(r for r in race.runners if r.number == 1)
    assert runner1.name == "Rapid Rover"
    assert runner1.odds['GBGB'].win == Decimal("3.5")

    runner2 = next(r for r in race.runners if r.number == 2)
    assert runner2.name == "Speedy Sue"
    assert runner2.odds['GBGB'].win == Decimal("2.0")

    runner3 = next(r for r in race.runners if r.number == 3)
    assert runner3.name == "Lazy Larry"
    assert runner3.odds['GBGB'].win == Decimal("11.0")

@pytest.mark.asyncio
async def test_get_races_handles_fetch_failure(gbgb_adapter):
    """
    Tests that get_races returns an empty list when _fetch_data returns None.
    """
    # ARRANGE
    mock_date = date.today().strftime('%Y-%m-%d')
    gbgb_adapter._fetch_data = AsyncMock(return_value=None)

    # ACT
    races = [race async for race in gbgb_adapter.get_races(mock_date)]

    # ASSERT
    assert races == []
