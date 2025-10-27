# tests/adapters/test_twinspires_adapter.py
import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from python_service.adapters.twinspires_adapter import TwinSpiresAdapter

@pytest.fixture
def twinspires_adapter():
    mock_config = MagicMock()
    return TwinSpiresAdapter(config=mock_config)

def read_fixture(file_path):
    with open(file_path, 'r') as f:
        return f.read()

@pytest.mark.asyncio
async def test_twinspires_adapter_get_races_successfully(twinspires_adapter):
    """Verify adapter correctly fetches and parses data via get_races."""
    mock_html = read_fixture('tests/fixtures/twinspires_sample.html')
    race_date = "2025-10-26"

    # Patch the internal _fetch_data method to return the mock HTML
    twinspires_adapter._fetch_data = AsyncMock(return_value={"html": mock_html, "date": race_date})

    races = [race async for race in twinspires_adapter.get_races(race_date)]

    assert len(races) == 1
    race = races[0]

    assert race.venue == "Churchill Downs"
    assert race.race_number == 5
    assert len(race.runners) == 3  # One runner is scratched

    braveheart = next((r for r in race.runners if r.name == 'Braveheart'), None)
    assert braveheart is not None
    assert braveheart.odds['TwinSpires'].win == Decimal('3.5')

    gallant_gus = next((r for r in race.runners if r.name == 'Gallant Gus'), None)
    assert gallant_gus is not None
    assert gallant_gus.odds['TwinSpires'].win == Decimal('4.0')

    # Check that the start time was parsed correctly
    assert race.start_time == datetime(2025, 10, 26, 16, 30)

@pytest.mark.asyncio
async def test_get_races_handles_fetch_failure(twinspires_adapter):
    """Tests that get_races returns an empty list when _fetch_data returns None."""
    race_date = "2025-10-26"
    twinspires_adapter._fetch_data = AsyncMock(return_value=None)

    races = [race async for race in twinspires_adapter.get_races(race_date)]

    assert races == []
