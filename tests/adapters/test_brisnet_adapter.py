# tests/adapters/test_brisnet_adapter.py
import pytest
import respx
import httpx
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock
from python_service.adapters.brisnet_adapter import BrisnetAdapter

@pytest.fixture
def brisnet_adapter():
    mock_config = MagicMock()
    return BrisnetAdapter(config=mock_config)

def read_fixture(file_path):
    with open(file_path, 'r') as f:
        return f.read()

@pytest.mark.asyncio
@respx.mock
async def test_brisnet_adapter_parses_html_correctly(brisnet_adapter):
    """Verify adapter correctly parses a known Brisnet HTML fixture."""
    mock_html = read_fixture('tests/fixtures/brisnet_sample.html')
    race_date = "2025-10-26"

    mock_route = respx.get(f"{brisnet_adapter.base_url}/race/{race_date}/CD").mock(
        return_value=httpx.Response(200, text=mock_html)
    )

    async with httpx.AsyncClient() as client:
        result = await brisnet_adapter.fetch_races(race_date, client)

    assert mock_route.called
    assert result["source_info"]["status"] == "SUCCESS"

    races = result["races"]
    assert len(races) == 1
    race = races[0]

    assert race["venue"] == "Churchill Downs"
    assert race["race_number"] == 5
    assert len(race["runners"]) == 2  # One is scratched

    starship = next((r for r in race["runners"] if r["name"] == 'Starship Enterprise'), None)
    assert starship is not None
    assert starship["odds"]['Brisnet']["win"] == Decimal('3.5')
