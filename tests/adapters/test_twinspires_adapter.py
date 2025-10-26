# tests/adapters/test_twinspires_adapter.py
import pytest
import respx
import httpx
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock
from python_service.adapters.twinspires_adapter import TwinSpiresAdapter

@pytest.fixture
def twinspires_adapter():
    mock_config = MagicMock()
    return TwinSpiresAdapter(config=mock_config)

def read_fixture(file_path):
    with open(file_path, 'r') as f:
        return f.read()

@pytest.mark.asyncio
@respx.mock
async def test_twinspires_adapter_fetch_races_successfully(twinspires_adapter):
    """Verify adapter correctly fetches and parses data."""
    mock_html = read_fixture('tests/fixtures/twinspires_sample.html')
    race_date = "2025-10-26"

    # Mock the HTTP request that the adapter will make
    mock_route = respx.get(f"{twinspires_adapter.base_url}/races/{race_date}").mock(
        return_value=httpx.Response(200, text=mock_html)
    )

    async with httpx.AsyncClient() as client:
        races = await twinspires_adapter.fetch_races(race_date, client)

    assert mock_route.called
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
