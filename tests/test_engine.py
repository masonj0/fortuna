import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, date
from decimal import Decimal
from tests.conftest import create_mock_race, get_test_settings

# Import your actual classes
from python_service.engine import OddsEngine
from python_service.adapters.base_adapter_v3 import BaseAdapterV3

@pytest.mark.asyncio
async def test_engine_initialization():
    """Test that the engine loads config correctly."""
    engine = OddsEngine(config=get_test_settings())
    assert engine.config.API_KEY == "test-override-key-123"

@pytest.mark.asyncio
async def test_fetch_all_odds_success(clear_cache):
    """Test happy path: fetching odds from a single adapter."""
    # ARRANGE
    engine = OddsEngine(config=get_test_settings())
    mock_adapter = AsyncMock(spec=BaseAdapterV3)
    mock_adapter.source_name = "MockSource"

    today = datetime.now()
    mock_race = create_mock_race(
        "MockSource", "Churchill Downs", 1, today,
        [{"number": 1, "name": "Secretariat", "odds": "1.5"}]
    )

    mock_adapter.get_races.return_value = [mock_race]
    engine.adapters = [mock_adapter]

    # ACT
    result = await engine.fetch_all_odds(date.today().strftime("%Y-%m-%d"))

    # ASSERT
    assert len(result["races"]) == 1
    assert result["races"][0]["venue"] == "Churchill Downs"
    assert result["races"][0]["runners"][0]["name"] == "Secretariat"

@pytest.mark.asyncio
async def test_fetch_all_odds_resilience(clear_cache):
    """Test that one failing adapter does not crash the whole engine."""
    # ARRANGE
    engine = OddsEngine(config=get_test_settings())

    # Adapter 1: Success
    good_adapter = AsyncMock(spec=BaseAdapterV3)
    good_adapter.source_name = "GoodSource"
    good_adapter.get_races.return_value = [
        create_mock_race("GoodSource", "Track A", 1, datetime.now(), [])
    ]

    # Adapter 2: Failure
    bad_adapter = AsyncMock(spec=BaseAdapterV3)
    bad_adapter.source_name = "BadSource"
    bad_adapter.get_races.side_effect = Exception("API Down")

    engine.adapters = [good_adapter, bad_adapter]

    # ACT
    result = await engine.fetch_all_odds("2025-12-08")

    # ASSERT
    assert len(result["races"]) == 1, "Should return data from the good adapter"
    assert result["races"][0]["source"] == "GoodSource"

    # Verify error logging in sourceInfo
    bad_info = next((s for s in result["sourceInfo"] if s["name"] == "BadSource"), None)
    assert bad_info is not None
    assert bad_info["status"] == "FAILED"

@pytest.mark.asyncio
async def test_race_aggregation_and_deduplication(clear_cache):
    """Test merging identical races from different sources."""
    engine = OddsEngine(config=get_test_settings())
    now = datetime.now()

    # Same race, different sources, slightly different odds
    race_a = create_mock_race("SourceA", "Ascot", 1, now, [{"number": 1, "name": "Horse X", "odds": "2.0"}])
    race_b = create_mock_race("SourceB", "Ascot", 1, now, [{"number": 1, "name": "Horse X", "odds": "2.2"}])

    adapter_a = AsyncMock(spec=BaseAdapterV3)
    adapter_a.source_name = "SourceA"
    adapter_a.get_races.return_value = [race_a]

    adapter_b = AsyncMock(spec=BaseAdapterV3)
    adapter_b.source_name = "SourceB"
    adapter_b.get_races.return_value = [race_b]

    engine.adapters = [adapter_a, adapter_b]

    # ACT
    result = await engine.fetch_all_odds("2025-12-08")

    # ASSERT
    assert len(result["races"]) == 1, "Should deduplicate into a single race object"
    merged_race = result["races"][0]
    runner = merged_race["runners"][0]

    # Check that odds from both sources are present
    # Note: This assertion depends on how your engine merges odds.
    # If it merges into a dict, this passes. If it overwrites, adjust accordingly.
    odds_keys = runner["odds"].keys()
    assert "SourceA" in odds_keys
    assert "SourceB" in odds_keys