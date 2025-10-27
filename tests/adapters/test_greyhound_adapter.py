import pytest
from unittest.mock import AsyncMock
from datetime import date, datetime
from python_service.adapters.greyhound_adapter import GreyhoundAdapter
from python_service.config import Settings

@pytest.fixture
def mock_config():
    """
    Provides a mock config object for the adapter.
    """
    return Settings(GREYHOUND_API_URL="https://api.example.com")

@pytest.mark.asyncio
async def test_get_races_parses_correctly(mock_config):
    """
    Tests that the GreyhoundAdapter correctly parses a valid API response via get_races.
    """
    # ARRANGE
    adapter = GreyhoundAdapter(config=mock_config)
    today = date.today().strftime('%Y-%m-%d')

    mock_api_response = {
        "cards": [
            {
                "track_name": "Test Track",
                "races": [
                    {
                        "race_id": "test_race_123",
                        "race_number": 1,
                        "start_time": int(datetime.now().timestamp()),
                        "runners": [
                            {"dog_name": "Rapid Rover", "trap_number": 1, "odds": {"win": "2.5"}},
                            {"dog_name": "Swift Sprint", "trap_number": 2, "scratched": True},
                            {"dog_name": "Lazy Larry", "trap_number": 3, "odds": {"win": "10.0"}},
                        ],
                    }
                ],
            }
        ]
    }
    adapter._fetch_data = AsyncMock(return_value=mock_api_response)

    # ACT
    races = [race async for race in adapter.get_races(today)]

    # ASSERT
    assert len(races) == 1
    race = races[0]
    assert race.id == 'greyhound_test_race_123'
    assert race.venue == 'Test Track'
    assert len(race.runners) == 2  # One was scratched

    runner1 = race.runners[0]
    assert runner1.name == 'Rapid Rover'
    assert runner1.number == 1
    assert runner1.odds['Greyhound Racing'].win == 2.5

@pytest.mark.asyncio
async def test_get_races_handles_empty_response(mock_config):
    """
    Tests that the GreyhoundAdapter handles an empty API response gracefully.
    """
    # ARRANGE
    adapter = GreyhoundAdapter(config=mock_config)
    today = date.today().strftime('%Y-%m-%d')
    adapter._fetch_data = AsyncMock(return_value={"cards": []})

    # ACT
    races = [race async for race in adapter.get_races(today)]

    # ASSERT
    assert races == []

@pytest.mark.asyncio
async def test_get_races_handles_fetch_failure(mock_config):
    """
    Tests that get_races returns an empty list when _fetch_data returns None.
    """
    # ARRANGE
    adapter = GreyhoundAdapter(config=mock_config)
    today = date.today().strftime('%Y-%m-%d')
    adapter._fetch_data = AsyncMock(return_value=None)

    # ACT
    races = [race async for race in adapter.get_races(today)]

    # ASSERT
    assert races == []
