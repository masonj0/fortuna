# tests/adapters/test_twinspires_adapter.py
import pytest
from python_service.adapters.twinspires_adapter import TwinSpiresAdapter
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
import pytest

from python_service.adapters.twinspires_adapter import TwinSpiresAdapter
from python_service.models import Race

# A mock settings object to satisfy the adapter's config dependency
class MockSettings:
    pass

@pytest.fixture
def adapter():
    return TwinSpiresAdapter(config=MockSettings())

@pytest.mark.asyncio
async def test_get_races_from_fixture(adapter, mocker):
    """
    Test that the adapter can correctly parse a local HTML fixture.
    This test validates the end-to-end parsing logic, including runner data,
    using the offline implementation.
    """
    # Mock the async fetch method to return a controlled response
    mock_response = mocker.MagicMock()
    mock_response.status = 200
    mock_response.text = Path("tests/fixtures/twinspires_racecard.html").read_text()

    adapter._fetch_with_retry = AsyncMock(return_value=mock_response)

    # Call the method under test
    races = await adapter.get_races(date="2025-11-12")

    # Assertions
    assert isinstance(races, list)
    assert len(races) == 1

    # Check the race for correct parsing
    race = races[0]
    assert race.venue == "Churchill Downs"
    assert race.race_number == 5

    # Check that runners were parsed correctly
    assert len(race.runners) == 4

    # Verify a specific runner's details
    runner_1 = next((r for r in race.runners if r.number == 1), None)
    assert runner_1 is not None
    assert runner_1.name == "Braveheart"
    assert not runner_1.scratched
    assert runner_1.odds["TwinSpires"].win == 3.5

    # Verify a scratched runner
    runner_3 = next((r for r in race.runners if r.number == 3), None)
    assert runner_3 is not None
    assert runner_3.name == "Steady Eddy"
    assert runner_3.scratched
    assert not runner_3.odds
