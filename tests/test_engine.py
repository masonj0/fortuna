import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, date
from decimal import Decimal
from tests.conftest import create_mock_race, get_test_settings

# Import your actual classes
from python_service.engine import OddsEngine
from python_service.adapters.base_adapter_v3 import BaseAdapterV3
from python_service.models import Race

@pytest.mark.asyncio
async def test_engine_initialization():
    """Test that the engine loads config correctly."""
    engine = OddsEngine(config=get_test_settings())
    assert engine.config.API_KEY == "test-override-key-123"

@pytest.mark.asyncio
@patch("python_service.engine.OddsEngine._time_adapter_fetch")
async def test_fetch_all_odds_success(mock_fetch, clear_cache):
    """Test happy path: fetching odds from a single adapter."""
    # ARRANGE
    settings = get_test_settings()
    settings.CACHE_ENABLED = False
    engine = OddsEngine(config=settings)

    today = datetime.now()
    mock_race = Race(**create_mock_race(
        "MockSource", "Churchill Downs", 1, today,
        [{"number": 1, "name": "Secretariat", "odds": "1.5"}]
    ))

    # This is the new way to mock the data
    mock_fetch.return_value = ("MockSource", {"races": [mock_race], "source_info": {"name": "MockSource", "status": "SUCCESS", "races_fetched": 1, "fetch_duration": 0.1}}, 0.1)

    # We still need to give the engine an adapter to iterate over
    mock_adapter = MagicMock(spec=BaseAdapterV3)
    mock_adapter.source_name = "MockSource"
    engine.adapters = {"MockSource": mock_adapter}
    # Update health monitor status for this mock adapter
    from python_service.adapter_manager import AdapterStatus, AdapterHealth
    engine.health_monitor.statuses["MockSource"] = AdapterStatus(
        name="MockSource",
        health=AdapterHealth.HEALTHY,
        success_rate_24h=1.0,
        last_success=None,
        consecutive_failures=0,
        avg_response_time_ms=0,
        last_error=None
    )

    # ACT
    result = await engine.fetch_all_odds(date.today().strftime("%Y-%m-%d"))

    # ASSERT
    assert len(result["races"]) == 1
    assert result["races"][0]["venue"] == "Churchill Downs"
    assert result["races"][0]["runners"][0]["name"] == "Secretariat"

@pytest.mark.asyncio
@patch("python_service.engine.OddsEngine._time_adapter_fetch")
async def test_fetch_all_odds_resilience(mock_fetch, clear_cache):
    """Test that one failing adapter does not crash the whole engine."""
    # ARRANGE
    settings = get_test_settings()
    settings.CACHE_ENABLED = False
    engine = OddsEngine(config=settings)

    # Mock successful adapter data
    good_race = Race(**create_mock_race("GoodSource", "Track A", 1, datetime.now(), []))
    good_payload = ("GoodSource", {"races": [good_race], "source_info": {"name": "GoodSource", "status": "SUCCESS", "races_fetched": 1, "fetch_duration": 0.1}}, 0.1)

    # Mock failed adapter data
    bad_payload = ("BadSource", {"races": [], "source_info": {"name": "BadSource", "status": "FAILED", "error_message": "API Down", "races_fetched": 0, "fetch_duration": 0.1}}, 0.1)

    mock_fetch.side_effect = [good_payload, bad_payload]

    # We still need to give the engine adapters to iterate over
    good_adapter = MagicMock(spec=BaseAdapterV3); good_adapter.source_name = "GoodSource"
    bad_adapter = MagicMock(spec=BaseAdapterV3); bad_adapter.source_name = "BadSource"
    engine.adapters = {"GoodSource": good_adapter, "BadSource": bad_adapter}
    # Update health monitor status
    from python_service.adapter_manager import AdapterStatus, AdapterHealth
    engine.health_monitor.statuses["GoodSource"] = AdapterStatus(
        name="GoodSource", health=AdapterHealth.HEALTHY,
        success_rate_24h=1.0, last_success=None, consecutive_failures=0, avg_response_time_ms=0, last_error=None
    )
    engine.health_monitor.statuses["BadSource"] = AdapterStatus(
        name="BadSource", health=AdapterHealth.HEALTHY,
        success_rate_24h=1.0, last_success=None, consecutive_failures=0, avg_response_time_ms=0, last_error=None
    )

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
@patch("python_service.engine.OddsEngine._time_adapter_fetch")
async def test_race_aggregation_and_deduplication(mock_fetch, clear_cache):
    """Test merging identical races from different sources."""
    settings = get_test_settings()
    settings.CACHE_ENABLED = False
    engine = OddsEngine(config=settings)
    now = datetime.now()

    # Same race, different sources, slightly different odds
    race_a = Race(**create_mock_race("SourceA", "Ascot", 1, now, [{"number": 1, "name": "Horse X", "odds": "2.0"}]))
    race_b = Race(**create_mock_race("SourceB", "Ascot", 1, now, [{"number": 1, "name": "Horse X", "odds": "2.2"}]))

    payload_a = ("SourceA", {"races": [race_a], "source_info": {"name": "SourceA", "status": "SUCCESS", "races_fetched": 1, "fetch_duration": 0.1}}, 0.1)
    payload_b = ("SourceB", {"races": [race_b], "source_info": {"name": "SourceB", "status": "SUCCESS", "races_fetched": 1, "fetch_duration": 0.1}}, 0.1)
    mock_fetch.side_effect = [payload_a, payload_b]

    adapter_a = MagicMock(spec=BaseAdapterV3); adapter_a.source_name = "SourceA"
    adapter_b = MagicMock(spec=BaseAdapterV3); adapter_b.source_name = "SourceB"
    engine.adapters = {"SourceA": adapter_a, "SourceB": adapter_b}
    # Update health monitor status
    from python_service.adapter_manager import AdapterStatus, AdapterHealth
    engine.health_monitor.statuses["SourceA"] = AdapterStatus(
        name="SourceA", health=AdapterHealth.HEALTHY,
        success_rate_24h=1.0, last_success=None, consecutive_failures=0, avg_response_time_ms=0, last_error=None
    )
    engine.health_monitor.statuses["SourceB"] = AdapterStatus(
        name="SourceB", health=AdapterHealth.HEALTHY,
        success_rate_24h=1.0, last_success=None, consecutive_failures=0, avg_response_time_ms=0, last_error=None
    )


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