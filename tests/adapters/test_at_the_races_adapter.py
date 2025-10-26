# tests/adapters/test_at_the_races_adapter.py
import pytest
import respx
import httpx
from datetime import datetime
from unittest.mock import MagicMock
from python_service.adapters.at_the_races_adapter import AtTheRacesAdapter

@pytest.fixture
def atr_adapter():
    mock_config = MagicMock()
    return AtTheRacesAdapter(config=mock_config)

def read_fixture(file_path):
    with open(file_path, 'r') as f:
        return f.read()

@pytest.mark.asyncio
@respx.mock
async def test_atr_adapter_hybrid_approach_successfully(atr_adapter):
    """Verify adapter correctly uses mobile overview and desktop detail pages."""
    mock_overview_html = read_fixture('tests/fixtures/at_the_races_mobile_sample.html')
    mock_detail_html = read_fixture('tests/fixtures/at_the_races_detail_sample.html')

    # Mock the overview page request
    respx.get(f"{atr_adapter.mobile_url}/racecards").mock(
        return_value=httpx.Response(200, text=mock_overview_html)
    )

    # Mock the detail page requests that will be triggered
    respx.get(f"{atr_adapter.base_url}/racecard/Fontwell/26-October-2025/1222").mock(
        return_value=httpx.Response(200, text=mock_detail_html)
    )
    respx.get(f"{atr_adapter.base_url}/racecard/Fontwell/26-October-2025/1257").mock(
        return_value=httpx.Response(200, text=mock_detail_html) # Re-use fixture for simplicity
    )
    respx.get(f"{atr_adapter.base_url}/racecard/Aintree/26-October-2025/1240").mock(
        return_value=httpx.Response(200, text=mock_detail_html.replace("Fontwell Park", "Aintree")) # Make venue unique for this test
    )

    async with httpx.AsyncClient() as client:
        races = await atr_adapter.fetch_races(datetime.now().strftime("%Y-%m-%d"), client)

    assert len(races) == 3

    fontwell_race_1 = next((r for r in races if r.venue == "Fontwell Park" and r.start_time.hour == 12), None)
    assert fontwell_race_1 is not None

    # Verify data from overview page
    assert fontwell_race_1.field_size == 6

    # Verify data from detail page
    assert len(fontwell_race_1.runners) == 2
    assert fontwell_race_1.runners[0].name == "Brave Knight"
    assert fontwell_race_1.race_number == 1

    aintree_race = next((r for r in races if r.venue == "Aintree"), None)
    assert aintree_race is not None
    assert aintree_race.field_size == 12
    assert len(aintree_race.runners) == 2 # From the re-used fixture
