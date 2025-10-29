import pytest
from unittest.mock import AsyncMock
from datetime import date, datetime, timezone
from decimal import Decimal

from python_service.adapters.the_racing_api_adapter import TheRacingApiAdapter
from python_service.core.exceptions import AdapterConfigError
from python_service.config import Settings

@pytest.fixture
def mock_config():
    """Provides a mock config object with the necessary API key."""
    return Settings(THE_RACING_API_KEY="test_racing_api_key")

@pytest.fixture
def mock_config_no_key():
    """Provides a mock config with the API key explicitly set to None."""
    return Settings(THE_RACING_API_KEY=None)

def test_init_raises_config_error_if_no_key(mock_config_no_key):
    """
    Tests that the adapter raises an AdapterConfigError if the API key is not set.
    """
    with pytest.raises(AdapterConfigError) as excinfo:
        TheRacingApiAdapter(config=mock_config_no_key)
    assert "THE_RACING_API_KEY is not configured" in str(excinfo.value)

@pytest.mark.asyncio
async def test_get_races_parses_correctly(mock_config):
    """
    Tests that TheRacingApiAdapter correctly parses a valid API response via get_races.
    """
    # ARRANGE
    adapter = TheRacingApiAdapter(config=mock_config)
    today = date.today().strftime('%Y-%m-%d')
    off_time = datetime.now(timezone.utc)

    mock_api_response = {
        "racecards": [{"race_id": "12345", "course": "Newbury", "race_no": 3, "off_time": off_time.isoformat().replace('+00:00', 'Z'),
                       "race_name": "The Great Race", "distance_f": "1m 2f", "runners": [
                           {"horse": "Speedy Steed", "number": 1, "jockey": "T. Rider", "trainer": "A. Trainer", "odds": [{"odds_decimal": "5.50"}]},
                           {"horse": "Gallant Gus", "number": 2, "jockey": "J. Jockey", "trainer": "B. Builder", "odds": [{"odds_decimal": "3.25"}]}
                       ]}]
    }

    # Patch the internal _fetch_data method
    adapter._fetch_data = AsyncMock(return_value=mock_api_response)

    # ACT
    races = [race async for race in adapter.get_races(today)]

    # ASSERT
    assert len(races) == 1
    race = races[0]
    assert race.id == 'tra_12345'
    assert race.venue == "Newbury"
    assert len(race.runners) == 2
    runner1 = race.runners[0]
    assert runner1.name == "Speedy Steed"
    assert runner1.odds[adapter.source_name].win == Decimal("5.50")

@pytest.mark.asyncio
async def test_get_races_handles_empty_response(mock_config):
    """
    Tests that the adapter returns an empty list for an API response with no racecards.
    """
    # ARRANGE
    adapter = TheRacingApiAdapter(config=mock_config)
    today = date.today().strftime('%Y-%m-%d')
    adapter._fetch_data = AsyncMock(return_value={"racecards": []})

    # ACT
    races = [race async for race in adapter.get_races(today)]

    # ASSERT
    assert races == []

@pytest.mark.asyncio
async def test_get_races_raises_exception_on_api_failure(mock_config):
    """
    Tests that get_races propagates the exception when _fetch_data fails.
    This is the desired behavior for the OddsEngine to handle it.
    """
    # ARRANGE
    adapter = TheRacingApiAdapter(config=mock_config)
    today = date.today().strftime('%Y-%m-%d')
    adapter._fetch_data = AsyncMock(side_effect=Exception("API is down"))

    # ACT & ASSERT
    with pytest.raises(Exception, match="API is down"):
        _ = [race async for race in adapter.get_races(today)]
