# python_service/engine.py

import asyncio
from copy import deepcopy
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Tuple

import json

import httpx
import redis
import redis.asyncio as redis_async
import structlog
from pydantic import ValidationError

from .adapters.at_the_races_adapter import AtTheRacesAdapter
from .adapters.base_v3 import BaseAdapterV3
from .adapters.betfair_adapter import BetfairAdapter
from .adapters.betfair_datascientist_adapter import BetfairDataScientistAdapter
from .adapters.betfair_greyhound_adapter import BetfairGreyhoundAdapter
from .adapters.brisnet_adapter import BrisnetAdapter
from .adapters.drf_adapter import DRFAdapter
from .adapters.equibase_adapter import EquibaseAdapter
from .adapters.fanduel_adapter import FanDuelAdapter
from .adapters.gbgb_api_adapter import GbgbApiAdapter
from .adapters.greyhound_adapter import GreyhoundAdapter
from .adapters.harness_adapter import HarnessAdapter
from .adapters.horseracingnation_adapter import HorseRacingNationAdapter
from .adapters.nyrabets_adapter import NYRABetsAdapter
from .adapters.oddschecker_adapter import OddscheckerAdapter
from .adapters.pointsbet_greyhound_adapter import PointsBetGreyhoundAdapter
from .adapters.punters_adapter import PuntersAdapter
from .adapters.racing_and_sports_adapter import RacingAndSportsAdapter
from .adapters.racing_and_sports_greyhound_adapter import (
    RacingAndSportsGreyhoundAdapter,
)
from .adapters.racingpost_adapter import RacingPostAdapter
from .adapters.racingtv_adapter import RacingTVAdapter
from .adapters.sporting_life_adapter import SportingLifeAdapter
from .adapters.tab_adapter import TabAdapter
from .adapters.the_racing_api_adapter import TheRacingApiAdapter
from .adapters.timeform_adapter import TimeformAdapter
from .adapters.twinspires_adapter import TwinSpiresAdapter
from .adapters.tvg_adapter import TVGAdapter
from .adapters.xpressbet_adapter import XpressbetAdapter
from .config import get_settings
from .core.exceptions import AdapterConfigError
from .core.exceptions import AdapterHttpError
from .manual_override_manager import ManualOverrideManager
from .models import AggregatedResponse
from .models import Race

log = structlog.get_logger(__name__)


class OddsEngine:
    def __init__(
        self,
        config=None,
        manual_override_manager: ManualOverrideManager = None,
        connection_manager=None,
    ):
        self.logger = structlog.get_logger(__name__)
        self.logger.info("Initializing FortunaEngine...")
        self.connection_manager = connection_manager
        self.redis_client = None
        self.use_redis = False
        self._memory_cache = {}  # The in-memory fallback cache

        try:
            try:
                self.config = config or get_settings()
                self.logger.info("Configuration loaded.")
            except ValidationError as e:
                self.logger.warning(
                    "Could not load settings, possibly in test environment.",
                    error=str(e),
                )
                # Create a default/mock config or re-raise if not in a test context
                from .config import Settings

                self.config = Settings(
                    API_KEY="a_secure_test_api_key_that_is_long_enough"
                )

            # --- Redis Initialization with Fallback ---
            try:
                # Attempt to connect with a short timeout
                self.redis_client = redis_async.from_url(
                    self.config.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2,
                )
                # Ping the server to confirm connectivity
                # Note: This is a synchronous ping for startup validation
                if redis.Redis.from_url(self.config.REDIS_URL).ping():
                    self.use_redis = True
                    self.logger.info("✅ Redis connection successful. Caching is enabled.")
                else:
                    raise ConnectionError("Redis ping failed.")
            except Exception as e:
                self.logger.warning(
                    f"⚠️ Redis unavailable, falling back to in-memory cache. Reason: {e}"
                )
                self.redis_client = None
                self.use_redis = False

            self.logger.info("Initializing adapters...")
            self.adapters: List[BaseAdapterV3] = []
            adapter_classes = [
                AtTheRacesAdapter,
                BetfairAdapter,
                BetfairGreyhoundAdapter,
                BrisnetAdapter,
                DRFAdapter,
                EquibaseAdapter,
                FanDuelAdapter,
                GbgbApiAdapter,
                GreyhoundAdapter,
                HarnessAdapter,
                HorseRacingNationAdapter,
                NYRABetsAdapter,
                OddscheckerAdapter,
                PuntersAdapter,
                RacingAndSportsAdapter,
                RacingAndSportsGreyhoundAdapter,
                RacingPostAdapter,
                RacingTVAdapter,
                SportingLifeAdapter,
                TabAdapter,
                TheRacingApiAdapter,
                TimeformAdapter,
                TwinSpiresAdapter,
                TVGAdapter,
                XpressbetAdapter,
                PointsBetGreyhoundAdapter,
            ]

            for adapter_cls in adapter_classes:
                try:
                    adapter_instance = adapter_cls(config=self.config)
                    if manual_override_manager and getattr(
                        adapter_instance, "supports_manual_override", False
                    ):
                        adapter_instance.enable_manual_override(manual_override_manager)
                    self.adapters.append(adapter_instance)
                except AdapterConfigError as e:
                    self.logger.warning(
                        "Skipping adapter due to configuration error",
                        adapter=adapter_cls.__name__,
                        error=str(e),
                    )
                except Exception:
                    self.logger.error(
                        f"An unexpected error occurred while initializing {adapter_cls.__name__}",
                        exc_info=True,
                    )

            # Special case for BetfairDataScientistAdapter with extra args
            try:
                bds_adapter = BetfairDataScientistAdapter(
                    model_name="ThoroughbredModel",
                    url="https://betfair-data-supplier-prod.herokuapp.com/api/widgets/kvs-ratings/datasets",
                    config=self.config,
                )
                if manual_override_manager and getattr(
                    bds_adapter, "supports_manual_override", False
                ):
                    bds_adapter.enable_manual_override(manual_override_manager)
                self.adapters.append(bds_adapter)
            except Exception:
                self.logger.warning(
                    "Failed to initialize adapter: BetfairDataScientistAdapter",
                    exc_info=True,
                )

            self.logger.info(f"{len(self.adapters)} adapters initialized successfully.")

            self.logger.info("Initializing HTTP client...")
            self.http_limits = httpx.Limits(
                max_connections=self.config.HTTP_POOL_CONNECTIONS,
                max_keepalive_connections=self.config.HTTP_MAX_KEEPALIVE,
            )
            self.http_client = httpx.AsyncClient(limits=self.http_limits, http2=True)
            self.logger.info("HTTP client initialized.")

            # Assign the shared client to each adapter
            for adapter in self.adapters:
                adapter.http_client = self.http_client

            # Initialize semaphore for concurrency limiting
            self.semaphore = asyncio.Semaphore(self.config.MAX_CONCURRENT_REQUESTS)
            self.logger.info(
                "Concurrency semaphore initialized",
                limit=self.config.MAX_CONCURRENT_REQUESTS,
            )

            self.logger.info("FortunaEngine initialization complete.")

        except Exception:
            self.logger.critical(
                "CRITICAL FAILURE during FortunaEngine initialization.", exc_info=True
            )
            raise

    async def close(self):
        await self.http_client.aclose()

    def get_all_adapter_statuses(self) -> List[Dict[str, Any]]:
        return [adapter.get_status() for adapter in self.adapters]

    async def get_from_cache(self, key):
        if self.use_redis and self.redis_client:
            try:
                return await self.redis_client.get(key)
            except Exception as e:
                self.logger.error(f"Redis GET failed, returning None. Error: {e}")
                return None
        else:
            return self._memory_cache.get(key)

    async def set_in_cache(self, key, value, ttl=300):
        if self.use_redis and self.redis_client:
            try:
                await self.redis_client.setex(key, ttl, value)
            except Exception as e:
                self.logger.error(f"Redis SET failed. Error: {e}")
        else:
            self._memory_cache[key] = value
            # Note: In-memory cache does not have TTL here, but this is a simple fallback.

    async def _fetch_with_semaphore(self, adapter: BaseAdapterV3, date: str):
        """Acquires the semaphore before fetching data from an adapter."""
        async with self.semaphore:
            return await self._time_adapter_fetch(adapter, date)

    async def _time_adapter_fetch(
        self, adapter: BaseAdapterV3, date: str
    ) -> Tuple[str, Dict[str, Any], float]:
        """
        Wraps a V3 adapter's fetch call for safe, non-blocking execution,
        and returns a consistent payload with timing information.
        """
        start_time = datetime.now()
        races: List[Race] = []
        error_message = None
        is_success = False
        attempted_url = None

        try:
            races = [race async for race in adapter.get_races(date)]
            is_success = True
        except AdapterHttpError as e:
            self.logger.error(
                "HTTP failure during fetch from adapter.",
                adapter=adapter.source_name,
                status_code=e.status_code,
                url=e.url,
                exc_info=False,
            )
            error_message = f"HTTP Error {e.status_code} for {e.url}"
            attempted_url = e.url
        except Exception as e:
            self.logger.error(
                "Critical failure during fetch from adapter.",
                adapter=adapter.source_name,
                error=str(e),
                exc_info=True,
            )
            error_message = str(e)

        duration = (datetime.now() - start_time).total_seconds()

        payload = {
            "races": races,
            "source_info": {
                "name": adapter.source_name,
                "status": "SUCCESS" if is_success else "FAILED",
                "races_fetched": len(races),
                "error_message": error_message,
                "fetch_duration": duration,
                "attempted_url": attempted_url,
            },
        }
        return (adapter.source_name, payload, duration)

    def _race_key(self, race: Race) -> str:
        return f"{race.venue.lower().strip()}|{race.race_number}|{race.start_time.strftime('%H:%M')}"

    def _dedupe_races(self, races: List[Race]) -> List[Race]:
        """Deduplicates races and reconciles odds from different sources."""
        races_copy = deepcopy(races)
        race_map: Dict[str, Race] = {}
        for race in races_copy:
            key = self._race_key(race)
            if key not in race_map:
                race_map[key] = race
            else:
                existing_race = race_map[key]
                runner_map = {r.number: r for r in existing_race.runners}
                for new_runner in race.runners:
                    if new_runner.number in runner_map:
                        existing_runner = runner_map[new_runner.number]
                        existing_runner.odds.update(new_runner.odds)
                    else:
                        existing_race.runners.append(new_runner)
                existing_race.source += f", {race.source}"

        return list(race_map.values())

    async def _broadcast_update(self, data: Dict[str, Any]):
        """Helper to broadcast data if the connection manager is available."""
        if self.connection_manager:
            await self.connection_manager.broadcast(data)

    async def fetch_all_odds(
        self, date: str, source_filter: str = None
    ) -> Dict[str, Any]:
        """
        Fetches and aggregates race data from all configured adapters.
        The result of this method is cached and broadcasted via WebSocket.
        """
        # Construct a cache key
        cache_key = f"fortuna_engine_races:{date}:{source_filter or 'all'}"
        cached_data = await self.get_from_cache(cache_key)
        if cached_data:
            log.info("Cache hit for fetch_all_odds", key=cache_key)
            return json.loads(cached_data)

        log.info("Cache miss for fetch_all_odds", key=cache_key)
        target_adapters = self.adapters
        if source_filter:
            log.info("Applying source filter", source=source_filter)
            target_adapters = [
                a
                for a in self.adapters
                if a.source_name.lower() == source_filter.lower()
            ]

        tasks = [
            self._fetch_with_semaphore(adapter, date) for adapter in target_adapters
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        source_infos = []
        all_races = []

        for result in results:
            if isinstance(result, Exception):
                log.error("Adapter fetch task failed", error=result, exc_info=False)
                continue

            _adapter_name, adapter_result, _duration = result
            source_info = adapter_result.get("source_info", {})
            source_infos.append(source_info)
            if source_info.get("status") == "SUCCESS":
                all_races.extend(adapter_result.get("races", []))

        deduped_races = self._dedupe_races(all_races)

        response_obj = AggregatedResponse(
            date=datetime.strptime(date, "%Y-%m-%d").date(),
            races=deduped_races,
            source_info=source_infos,
            metadata={
                "fetch_time": datetime.now(),
                "sources_queried": [a.source_name for a in target_adapters],
                "sources_successful": len(
                    [s for s in source_infos if s["status"] == "SUCCESS"]
                ),
                "total_races": len(deduped_races),
            },
        )

        response_data = response_obj.model_dump(by_alias=True)

        # Set the result in the cache
        await self.set_in_cache(
            cache_key, json.dumps(response_data, default=str), ttl=300
        )
        await self._broadcast_update(response_data)
        return response_data
