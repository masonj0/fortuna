# tests/test_engine.py

from datetime import date
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import fakeredis
import httpx
import pytest
from python_service.adapters.base_v3 import BaseAdapterV3
from tenacity import RetryError

from python_service.core.exceptions import AdapterHttpError
from python_service.engine import OddsEngine
from python_service.models import Race
from tests.conftest import get_test_settings
from tests.utils import create_mock_race


@pytest.mark.asyncio
async def test_engine_initialization():
    """
    SPEC: The OddsEngine should initialize without errors and load adapters correctly.
    """
    engine = OddsEngine(config=get_test_settings())
    assert len(engine.adapters) > 0, "Adapters should be loaded"
    assert "betfair_adapter" in [a.source_name for a in engine.adapters], "Betfair adapter should be loaded"


@pytest.mark.asyncio
async def test_fetch_all_odds_success():
    """
    SPEC: The OddsEngine should fetch data from all adapters and aggregate the results.
    """
    engine = OddsEngine(config=get_test_settings())
    mock_adapter = AsyncMock(spec=BaseAdapterV3)
    mock_adapter.source_name = "MockAdapter"
    mock_adapter.get_races.return_value = [create_mock_race("MockSource", "Race 1", 1, datetime.now(), [])]
    engine.adapters = [mock_adapter]

    today_str = date.today().strftime("%Y-%m-%d")
    result = await engine.fetch_all_odds(today_str)

    assert "races" in result
    assert "sources" in result
    assert len(result["races"]) == 1
    assert result["races"][0]["trackName"] == "Race 1"


@pytest.mark.asyncio
async def test_fetch_all_odds_resilience():
    """
    SPEC: The OddsEngine should be resilient to individual adapter failures.
          If one adapter fails, the engine should still return data from the others.
    """
    # ARRANGE
    engine = OddsEngine(config=get_test_settings())
    successful_adapter = AsyncMock(spec=BaseAdapterV3)
    successful_adapter.source_name = "SuccessAdapter"
    successful_adapter.get_races.return_value = [
        create_mock_race("SuccessSource", "Success Race", 1, datetime.now(), runners=[])
    ]

    failing_adapter = AsyncMock(spec=BaseAdapterV3)
    failing_adapter.source_name = "FailAdapter"
    failing_adapter.get_races.side_effect = AdapterHttpError("Mock HTTP Error", 500)

    engine.adapters = [successful_adapter, failing_adapter]
    today_str = date.today().strftime("%Y-%m-%d")

    # ACT
    result = await engine.fetch_all_odds(today_str)

    # ASSERT
    assert "races" in result
    assert "sources" in result
    assert len(result["races"]) == 1, "Should return data from the successful adapter"
    assert result["races"][0]["source"] == "SuccessSource"

    # Check that the failed adapter's status is correctly recorded
    adapter_statuses = engine.get_all_adapter_statuses()
    failed_adapter_status = next((s for s in adapter_statuses if s["source_name"] == "FailAdapter"), None)
    assert failed_adapter_status is not None, "Failed adapter status should be present"
    assert "Mock HTTP Error" in failed_adapter_status["error"], "Error message should be recorded"


@pytest.mark.asyncio
async def test_race_aggregation_and_deduplication():
    """
    SPEC: The OddsEngine should correctly aggregate and deduplicate races from
          multiple sources based on a unique race identifier (track, time, race number).
    """
    # ARRANGE
    engine = OddsEngine(config=get_test_settings())
    now = datetime.now()

    # Create two identical races from different sources
    race1_source1 = create_mock_race("Source1", "Pimlico", 1, now, [{"number": 1, "name": "Runner A", "odds": "2.5"}])
    race1_source2 = create_mock_race("Source2", "Pimlico", 1, now, [{"number": 1, "name": "Runner A", "odds": "2.8"}])

    # Create a unique race
    unique_race = create_mock_race("Source1", "Belmont", 2, now, [{"number": 2, "name": "Runner B", "odds": "5.0"}])

    adapter1 = AsyncMock(spec=BaseAdapterV3)
    adapter1.source_name = "Source1"
    adapter1.get_races.return_value = [race1_source1, unique_race]

    adapter2 = AsyncMock(spec=BaseAdapterV3)
    adapter2.source_name = "Source2"
    adapter2.get_races.return_value = [race1_source2]

    engine.adapters = [adapter1, adapter2]
    today_str = date.today().strftime("%Y-%m-%d")

    # ACT
    result = await engine.fetch_all_odds(today_str)

    # ASSERT
    assert len(result["races"]) == 2, "Should have two unique races after deduplication"

    # Find the aggregated race for Pimlico
    pimlico_race_data = next((r for r in result["races"] if r["trackName"] == "Pimlico"), None)
    assert pimlico_race_data is not None, "Pimlico race should be in the result"

    # Convert to Pydantic model for easier validation
    pimlico_race = Race(**pimlico_race_data)

    # Check runner odds aggregation
    runner = pimlico_race.runners[0]
    assert len(runner.odds) == 2, "Runner odds should be aggregated from two sources"
    assert runner.odds["Source1"].win == Decimal("2.5")
    assert runner.odds["Source2"].win == Decimal("2.8")

    # Check that the race's `sources` list is correct
    assert "Source1" in pimlico_race.sources
    assert "Source2" in pimlico_race.sources


@pytest.mark.asyncio
async def test_engine_caching_logic():
    """
    SPEC: The OddsEngine should cache results in Redis.
    1. On a cache miss, it should fetch from adapters and set the cache.
    2. On a cache hit, it should return data from the cache without fetching from adapters.
    """
    # ARRANGE
    # Use the asynchronous FakeRedis for the asynchronous CacheManager
    with patch("redis.from_url", fakeredis.aioredis.FakeRedis.from_url):
        import redis.asyncio as redis

        from python_service.cache_manager import cache_manager

        # Re-initialize the client on the singleton to use the patched async version
        cache_manager.redis_client = redis.from_url("redis://fake", decode_responses=True)
        assert cache_manager.redis_client is not None, "Failed to patch redis_client"

        engine = OddsEngine(config=get_test_settings())

        today_str = date.today().strftime("%Y-%m-%d")
        test_time = datetime(2025, 10, 9, 15, 0)
        mock_race = create_mock_race(
            "TestSource",
            "Cache Park",
            1,
            test_time,
            [{"number": 1, "name": "Cachedy", "odds": "4.0"}],
        )

        mock_adapter = AsyncMock(spec=BaseAdapterV3)
        mock_adapter.source_name = "TestSource"
        engine.adapters = [mock_adapter]  # Isolate to one mock adapter

        await cache_manager.redis_client.flushdb()

        # --- 1. Cache Miss ---
        # ARRANGE
        mock_adapter.get_races.return_value = [mock_race]
        mock_adapter.get_races.reset_mock()  # Reset call count

        # ACT
        result_miss = await engine.fetch_all_odds(today_str)

        # ASSERT
        mock_adapter.get_races.assert_awaited_once()  # Adapter was called
        assert len(result_miss["races"]) == 1
        assert result_miss["races"][0]["trackName"] == "Cache Park"

        # --- 2. Cache Hit ---
        # ARRANGE
        mock_adapter.get_races.reset_mock()

        # ACT
        result_hit = await engine.fetch_all_odds(today_str)

        # ASSERT
        mock_adapter.get_races.assert_not_awaited()  # Adapter was NOT called
        assert len(result_hit["races"]) == 1, "Should return data from cache on cache hit"
        assert result_hit["races"][0]["trackName"] == "Cache Park"


@pytest.mark.asyncio
async def test_http_client_tenacity_retry():
    """
    SPEC: The shared httpx client in BaseAdapterV3 should retry on transient HTTP errors.
    """
    # ARRANGE
    engine = OddsEngine(config=get_test_settings())
    # Find a real adapter instance to test with
    adapter_instance = next((a for a in engine.adapters if a.source_name == "at_the_races_adapter"), None)
    assert adapter_instance is not None, "Could not find a suitable adapter to test"

    # Mock the internal httpx client's request method to simulate failures
    mock_response = MagicMock()
    mock_response.status_code = 503  # Service Unavailable
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Service Unavailable", request=MagicMock(), response=mock_response
    )

    # Configure the mock to fail twice, then succeed
    adapter_instance.http_client.get = AsyncMock(
        side_effect=[
            mock_response,
            mock_response,
            AsyncMock(status_code=200, text="<html>Success</html>"),
        ]
    )

    # ACT & ASSERT
    try:
        # This call should succeed after two retries
        await adapter_instance._fetch_data("https://any.url")
    except RetryError:
        pytest.fail("The HTTP client did not successfully retry after transient errors")

    # ASSERT
    assert adapter_instance.http_client.get.call_count == 3, (
        "The client should have been called 3 times (1 initial + 2 retries)"
    )
