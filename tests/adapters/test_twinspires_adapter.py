# tests/adapters/test_twinspires_adapter.py
import pytest
from python_service.adapters.twinspires_adapter import TwinSpiresAdapter
from unittest.mock import MagicMock, AsyncMock
from pathlib import Path
from python_service.models import Race
from decimal import Decimal
from datetime import datetime, timedelta, timezone

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
    This test validates the end-to-end parsing logic, including runner data.
    """
    # ARRANGE
    future_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%d")
    fixture_path = Path("tests/fixtures/twinspires_racecard.html")
    html_content = fixture_path.read_text()

    # Mock the internal _fetch_data to return our fixture wrapped in the expected structure
    mock_raw_data = {
        "date": future_date,
        "source": "TwinSpires",
        "races": [
            {
                "html": html_content,
                "track": "Churchill Downs",
                "race_number": 5,
                "post_time_text": "05:05 PM",
                "date": future_date,
                "full_page": False
            }
        ]
    }

    adapter._fetch_data = AsyncMock(return_value=mock_raw_data)

    # ACT
    races = await adapter.get_races(date=future_date)

    # ASSERT
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
    # 5/2 = 2.5 + 1 = 3.5
    assert runner_1.odds["TwinSpires"].win == Decimal("3.5")

    # Verify a scratched runner
    runner_3 = next((r for r in race.runners if r.number == 3), None)
    assert runner_3 is not None
    assert runner_3.name == "Steady Eddy"
    assert runner_3.scratched
    assert not runner_3.odds
