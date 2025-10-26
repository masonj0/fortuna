# tests/adapters/test_drf_adapter.py
import pytest
import respx
import httpx
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock
from python_service.adapters.drf_adapter import DRFAdapter

@pytest.fixture
def drf_adapter():
    mock_config = MagicMock()
    return DRFAdapter(config=mock_config)

def read_fixture(file_path):
    with open(file_path, 'r') as f:
        return f.read()

@pytest.mark.asyncio
@respx.mock
async def test_drf_adapter_parses_html_correctly(drf_adapter):
    """Verify adapter correctly parses a known DRF HTML fixture."""
    mock_html = read_fixture('tests/fixtures/drf_sample.html')
    race_date = "2025-10-26"

    mock_route = respx.get(f"{drf_adapter.base_url}/entries/{race_date}/USA").mock(
        return_value=httpx.Response(200, text=mock_html)
    )

    async with httpx.AsyncClient() as client:
        result = await drf_adapter.fetch_races(race_date, client)

    assert mock_route.called
    assert result["source_info"]["status"] == "SUCCESS"

    races = result["races"]
    assert len(races) == 1
    race = races[0]

    assert race["venue"] == "Churchill Downs"
    assert race["race_number"] == 5
    assert len(race["runners"]) == 2  # One is scratched

    macho_macho = next((r for r in race["runners"] if r["name"] == 'Macho Macho'), None)
    assert macho_macho is not None
    assert macho_macho["odds"]['DRF']["win"] == Decimal('3.5')
