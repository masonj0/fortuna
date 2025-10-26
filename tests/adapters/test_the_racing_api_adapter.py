import pytest
import httpx
from unittest.mock import AsyncMock, Mock
from datetime import date, datetime
from decimal import Decimal

from python_service.adapters.the_racing_api_adapter import TheRacingApiAdapter
from python_service.core.exceptions import AdapterConfigError, AdapterHttpError
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
async def test_fetch_races_parses_correctly(mock_config):
    """
    Tests that TheRacingApiAdapter correctly parses a valid API response.
    """
    # ARRANGE
    adapter = TheRacingApiAdapter(config=mock_config)
    today = date.today().strftime('%Y-%m-%d')
    off_time_str = datetime.utcnow().isoformat() + "Z"

    mock_api_response = {
        "racecards": [{"race_id": "12345", "course": "Newbury", "race_no": 3, "off_time": off_time_str,
                       "race_name": "The Great Race", "distance_f": "1m 2f", "runners": [
                           {"horse": "Speedy Steed", "number": 1, "jockey": "T. Rider", "trainer": "A. Trainer", "odds": [{"odds_decimal": "5.50"}]},
                           {"horse": "Gallant Gus", "number": 2, "jockey": "J. Jockey", "trainer": "B. Builder", "odds": [{"odds_decimal": "3.25"}]}
                       ]}]
    }

    mock_http_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = Mock(spec=httpx.Response)
    mock_response.json.return_value = mock_api_response
    mock_http_client.request.return_value = mock_response

    # We patch make_request at the adapter instance level for simplicity
    adapter.make_request = AsyncMock(return_value=mock_response)

    # ACT
    races = await adapter.fetch_races(today, mock_http_client)

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
async def test_fetch_races_handles_empty_response(mock_config):
    """
    Tests that the adapter returns an empty list for an API response with no racecards.
    """
    # ARRANGE
    adapter = TheRacingApiAdapter(config=mock_config)
    today = date.today().strftime('%Y-%m-%d')

    mock_http_client = AsyncMock(spec=httpx.AsyncClient)
    mock_response = Mock(spec=httpx.Response)
    mock_response.json.return_value = {"racecards": []}
    mock_http_client.request.return_value = mock_response
    adapter.make_request = AsyncMock(return_value=mock_response)

    # ACT
    races = await adapter.fetch_races(today, mock_http_client)

    # ASSERT
    assert races == []

@pytest.mark.asyncio
async def test_fetch_races_returns_empty_list_on_api_failure(mock_config):
    """
    Tests that fetch_races returns an empty list when make_request fails,
    as the new base class orchestrator now handles the exception.
    """
    # ARRANGE
    adapter = TheRacingApiAdapter(config=mock_config)
    today = date.today().strftime('%Y-%m-%d')
    mock_http_client = AsyncMock(spec=httpx.AsyncClient)

    # Configure the mock to raise an exception, simulating a request failure
    adapter.make_request = AsyncMock(side_effect=AdapterHttpError(adapter.source_name, 500, "http://test.url"))

    # ACT
    result = await adapter.fetch_races(today, mock_http_client)

    # ASSERT
    # The new pattern handles the exception and returns an empty list
    assert result == []