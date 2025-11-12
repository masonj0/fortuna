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
from python_service.adapters.base_adapter_v3 import BaseAdapterV3
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
    assert "BetfairExchange" in [a.source_name for a in engine.adapters], "Betfair adapter should be loaded"


@pytest.mark.asyncio
async def test_fetch_all_odds_success():
    """
    SPEC: The OddsEngine should fetch data from all adapters and aggregate the results.
    """
    engine = OddsEngine(config=get_test_settings())
    mock_adapter = AsyncMock(spec=BaseAdapterV3)
    mock_adapter.source_name = "MockAdapter"

    # THE FIX: Return a list from an async function to match the expected adapter behavior.
    async def mock_get_races(*args, **kwargs):
        return [create_mock_race("MockSource", "Race 1", 1, datetime.now(), [])]

    mock_adapter.get_races = mock_get_races
    engine.adapters = [mock_adapter]

    today_str = date.today().strftime("%Y-%m-%d")
    result = await engine.fetch_all_odds(today_str)

    assert "races" in result
    # THE FIX: The model uses the alias 'sourceInfo', not 'sources'.
    assert "sourceInfo" in result
    assert len(result["races"]) == 1
    # THE FIX: The Pydantic model uses 'venue' internally.
    assert result["races"][0]["venue"] == "Race 1"


@pytest.mark.asyncio
async def test_fetch_all_odds_resilience(clear_cache):
    """
    SPEC: The OddsEngine should be resilient to individual adapter failures.
          If one adapter fails, the engine should still return data from the others.
    """
    # ARRANGE
    engine = OddsEngine(config=get_test_settings())
    successful_adapter = AsyncMock(spec=BaseAdapterV3)
    successful_adapter.source_name = "SuccessAdapter"

    async def mock_success_get_races(*args, **kwargs):
        return [create_mock_race("SuccessSource", "Success Race", 1, datetime.now(), [])]

    successful_adapter.get_races = mock_success_get_races

    failing_adapter = AsyncMock(spec=BaseAdapterV3)
    failing_adapter.source_name = "FailAdapter"
    # THE FIX: Provide all required arguments to the exception constructor.
    failing_adapter.get_races.side_effect = AdapterHttpError(
        "Mock HTTP Error", 500, "https://failed.url"
    )

    engine.adapters = [successful_adapter, failing_adapter]
    today_str = date.today().strftime("%Y-%m-%d")

    # ACT
    result = await engine.fetch_all_odds(today_str)

    # ASSERT
    assert "races" in result
    assert "sourceInfo" in result
    assert len(result["races"]) == 1, "Should return data from the successful adapter"
    assert result["races"][0]["source"] == "SuccessSource"

    # Check that the failed adapter's status is correctly recorded in the response
    failed_adapter_info = next((s for s in result["sourceInfo"] if s["name"] == "FailAdapter"), None)
    assert failed_adapter_info is not None, "Failed adapter status should be present in the response"
    assert failed_adapter_info["status"] == "FAILED", "Status should be FAILED"
    # THE FIX: The auto-generated error message contains the status and URL, which is sufficient.
    assert "500" in failed_adapter_info["errorMessage"]
    assert "failed.url" in failed_adapter_info["errorMessage"]


@pytest.mark.asyncio
async def test_race_aggregation_and_deduplication(clear_cache):
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

    async def mock_adapter1_get_races(*args, **kwargs):
        return [race1_source1, unique_race]

    adapter1.get_races = mock_adapter1_get_races

    adapter2 = AsyncMock(spec=BaseAdapterV3)
    adapter2.source_name = "Source2"

    async def mock_adapter2_get_races(*args, **kwargs):
        return [race1_source2]

    adapter2.get_races = mock_adapter2_get_races

    engine.adapters = [adapter1, adapter2]
    today_str = date.today().strftime("%Y-%m-%d")

    # ACT
    result = await engine.fetch_all_odds(today_str)

    # ASSERT
    assert len(result["races"]) == 2, "Should have two unique races after deduplication"

    # Find the aggregated race for Pimlico
    pimlico_race_data = next((r for r in result["races"] if r["venue"] == "Pimlico"), None)
    assert pimlico_race_data is not None, "Pimlico race should be in the result"

    # Convert to Pydantic model for easier validation
    pimlico_race = Race(**pimlico_race_data)

    # Check runner odds aggregation
    runner = pimlico_race.runners[0]
    assert len(runner.odds) == 2, "Runner odds should be aggregated from two sources"
    assert runner.odds["Source1"].win == Decimal("2.5")
    assert runner.odds["Source2"].win == Decimal("2.8")

    # Check that the race's `source` attribute is correct
    assert "Source1" in pimlico_race.source
    assert "Source2" in pimlico_race.source


@pytest.mark.asyncio
async def test_engine_caching_logic():
    """
    SPEC: The OddsEngine should cache results in Redis.
    1. On a cache miss, it should fetch from adapters and set the cache.
    2. On a cache hit, it should return data from the cache without fetching from adapters.
    """
    # ARRANGE
    # Use the asynchronous FakeRedis for the asynchronous CacheManager
    # THE FIX: The patch target must be the specific `from_url` used by the cache manager.
    # We also reload the module to ensure the singleton picks up the patched client.
    with patch("redis.asyncio.from_url", fakeredis.aioredis.FakeRedis.from_url):
        from importlib import reload
        from python_service import cache_manager
        reload(cache_manager)
        # THE FIX: Call connect() on the *instance* of the CacheManager, not the module.
        await cache_manager.cache_manager.connect("redis://dummy")


        # Initialize the engine *inside* the patch context to ensure it gets the
        # correctly mocked cache_manager instance.
        engine = OddsEngine(config=get_test_settings())
        assert engine.cache_manager.is_configured, "Cache manager should be configured with fake redis"

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

        # THE FIX: Access the redis_client on the singleton *instance*.
        await cache_manager.cache_manager.redis_client.flushdb()

        # --- 1. Cache Miss ---
        # ARRANGE
        async def mock_get_races(*args, **kwargs):
            return [mock_race]

        # THE FIX: Wrap the async generator in an AsyncMock to allow for resetting.
        mock_adapter.get_races = AsyncMock(side_effect=mock_get_races)
        mock_adapter.get_races.reset_mock()

        # ACT
        result_miss = await engine.fetch_all_odds(today_str)

        # ASSERT
        mock_adapter.get_races.assert_awaited_once()  # Adapter was called
        assert len(result_miss["races"]) == 1
        assert result_miss["races"][0]["venue"] == "Cache Park"

        # --- 2. Cache Hit ---
        # ARRANGE
        mock_adapter.get_races.reset_mock()

        # ACT
        result_hit = await engine.fetch_all_odds(today_str)

        # ASSERT
        mock_adapter.get_races.assert_not_awaited()  # Adapter was NOT called
        assert len(result_hit["races"]) == 1, "Should return data from cache on cache hit"
        assert result_hit["races"][0]["venue"] == "Cache Park"


@pytest.mark.asyncio
async def test_http_client_tenacity_retry():
    """
    SPEC: The BaseAdapterV3's make_request method should retry on transient errors.
    """
    # ARRANGE
    # Create an instance of a concrete adapter to test the shared `make_request`
    from python_service.adapters.betfair_adapter import BetfairAdapter
    adapter_instance = BetfairAdapter(config=get_test_settings())

    # Replace the http_client with a mock
    mock_http_client = AsyncMock(spec=httpx.AsyncClient)
    adapter_instance.http_client = mock_http_client

    # Configure the mock to simulate failures then success
    mock_http_client.request.side_effect = [
        httpx.ReadTimeout("Timeout!", request=MagicMock()),
        httpx.ConnectError("Connection failed!"),
        AsyncMock(spec=httpx.Response, status_code=200, text="Success"),
    ]

    # ACT & ASSERT
    try:
        # This call should succeed after two retries
        await adapter_instance.make_request(
            adapter_instance.http_client, "get", "https://any.url"
        )
    except RetryError:
        pytest.fail("The make_request method did not successfully retry after transient errors")

    # ASSERT
    assert mock_http_client.request.call_count == 3, (
        "The http_client.request method should have been called 3 times (1 initial + 2 retries)"
    )
