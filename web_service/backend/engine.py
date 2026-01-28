# python_service/engine.py

import asyncio
import json
from copy import deepcopy
from datetime import datetime
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

import httpx
import redis
import redis.asyncio as redis_async
import structlog
from pydantic import ValidationError

from .adapters import (
    AtTheRacesAdapter,
    AtTheRacesGreyhoundAdapter,
    BetfairAdapter,
    BetfairGreyhoundAdapter,
    BrisnetAdapter,
    EquibaseAdapter,
    FanDuelAdapter,
    GbgbApiAdapter,
    GreyhoundAdapter,
    HarnessAdapter,
    HorseRacingNationAdapter,
    NYRABetsAdapter,
    OddscheckerAdapter,
    PointsBetGreyhoundAdapter,
    PuntersAdapter,
    RacingAndSportsAdapter,
    RacingAndSportsGreyhoundAdapter,
    RacingPostAdapter,
    RacingTVAdapter,
    SportingLifeAdapter,
    TabAdapter,
    TheRacingApiAdapter,
    TimeformAdapter,
    TVGAdapter,
    TwinSpiresAdapter,
    UniversalAdapter,
    XpressbetAdapter,
)
from .adapters.base_adapter_v3 import BaseAdapterV3
from .config import get_settings
from .core.exceptions import AdapterConfigError
from .core.exceptions import AdapterHttpError
from .core.exceptions import AuthenticationError
from .adapter_manager import AdapterHealthMonitor, AdapterHealth, AdapterStatus
from .cache_manager import StaleDataCache
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
        exclude_adapters: Optional[List[str]] = None,
    ):
        # THE FIX: Import the cache_manager singleton here to ensure tests can
        # patch and reload it *before* the engine is initialized.
        from .cache_manager import cache_manager

        self.logger = structlog.get_logger(__name__)
        self.logger.info("Initializing FortunaEngine...")
        self.connection_manager = connection_manager
        self.cache_manager = cache_manager
        self.health_monitor = AdapterHealthMonitor()
        self.stale_data_cache = StaleDataCache(max_age_hours=24)
        self.exclude_adapters = set(exclude_adapters) if exclude_adapters else set()

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

                self.config = Settings(API_KEY="a_secure_test_api_key_that_is_long_enough")

            # Redis is now handled entirely by the CacheManager.

            self.logger.info("Initializing adapters...")
            self.adapters: Dict[str, BaseAdapterV3] = {}

            # NOTE: Many adapters require API keys (e.g., TVG, Betfair, TheRacingAPI).
            # If the required API key is not found in the environment configuration,
            # the adapter will fail to initialize and be skipped. This is expected
            # behavior in environments where secrets are not configured.
            adapter_classes = [
                AtTheRacesAdapter,
                AtTheRacesGreyhoundAdapter,
                BetfairAdapter,
                BetfairGreyhoundAdapter,
                BrisnetAdapter,
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
                UniversalAdapter,
                XpressbetAdapter,
                PointsBetGreyhoundAdapter,
            ]

            for adapter_cls in adapter_classes:
                adapter_name = adapter_cls.__name__
                if adapter_name in self.exclude_adapters:
                    self.logger.info(f"Intentionally skipping adapter: {adapter_name}")
                    continue
                try:
                    self.logger.info(f"Attempting to initialize adapter: {adapter_name}")
                    if adapter_name == "UniversalAdapter":
                        # UniversalAdapter requires a definition_path, which we don't have here.
                        # For now, we'll skip it unless it's explicitly configured.
                        self.logger.info("UniversalAdapter PoC requires a definition_path. Skipping.")
                        continue
                    adapter_instance = adapter_cls(config=self.config)
                    self.logger.info(f"Successfully initialized adapter: {adapter_name}")
                    if manual_override_manager and getattr(adapter_instance, "supports_manual_override", False):
                        adapter_instance.enable_manual_override(manual_override_manager)
                    self.adapters[adapter_instance.source_name] = adapter_instance
                except AdapterConfigError as e:
                    self.logger.warning(
                        "Skipping adapter due to configuration error",
                        adapter=adapter_name,
                        error=str(e),
                    )
                except Exception:
                    self.logger.error(
                        f"An unexpected error occurred while initializing {adapter_name}",
                        exc_info=True,
                    )

            for adapter_instance in self.adapters.values():
                self.health_monitor.statuses[adapter_instance.source_name] = AdapterStatus(
                    name=adapter_instance.source_name,
                    health=AdapterHealth.HEALTHY,
                    success_rate_24h=1.0,
                    last_success=None,
                    consecutive_failures=0,
                    avg_response_time_ms=0,
                    last_error=None,
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
            for adapter in self.adapters.values():
                adapter.http_client = self.http_client

            # Initialize semaphore for concurrency limiting
            self.semaphore = asyncio.Semaphore(self.config.MAX_CONCURRENT_REQUESTS)
            self.logger.info(
                "Concurrency semaphore initialized",
                limit=self.config.MAX_CONCURRENT_REQUESTS,
            )

            self.logger.info("FortunaEngine initialization complete.")

        except Exception:
            self.logger.critical("CRITICAL FAILURE during FortunaEngine initialization.", exc_info=True)
            raise

    async def close(self):
        await self.http_client.aclose()

    async def shutdown(self):
        """Gracefully shuts down all adapters that require cleanup."""
        self.logger.info("Shutting down adapters with cleanup methods...")
        for adapter_name, adapter in self.adapters.items():
            if hasattr(adapter, 'cleanup'):
                try:
                    self.logger.info(f"Cleaning up {adapter_name}...")
                    await adapter.cleanup()
                except Exception as e:
                    self.logger.error(f"Error cleaning up {adapter_name}", error=str(e), exc_info=True)
        await self.close()

    def get_all_adapter_statuses(self) -> List[Dict[str, Any]]:
        return [adapter.get_status() for adapter in self.adapters.values()]

    async def get_from_cache(self, key):
        return await self.cache_manager.get(key)

    async def set_in_cache(self, key, value, ttl=300):
        # THE FIX: The keyword argument is 'ttl_seconds', not 'ttl'.
        await self.cache_manager.set(key, value, ttl_seconds=ttl)

    async def _fetch_with_semaphore(self, adapter: BaseAdapterV3, date: str):
        """Acquires the semaphore before fetching data from an adapter."""
        async with self.semaphore:
            return await self._time_adapter_fetch(adapter, date)

    async def _time_adapter_fetch(self, adapter: BaseAdapterV3, date: str) -> Tuple[str, Dict[str, Any], float]:
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
            race_data_list = await adapter.get_races(date)
            processed_races = []
            for race_data in race_data_list:
                if isinstance(race_data, Race):
                    processed_races.append(race_data)
                else:
                    processed_races.append(Race(**race_data))
            races = processed_races
            if races:
                is_success = True
            else:
                is_success = False
                error_message = "Adapter ran successfully but fetched zero races."
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
            races = [
                Race(
                    id=f"error_{adapter.source_name.lower()}",
                    venue=adapter.source_name,
                    race_number=0,
                    start_time=datetime.now(),
                    runners=[],
                    source=adapter.source_name,
                    is_error_placeholder=True,
                    error_message=error_message,
                )
            ]
        except AuthenticationError as e:
            self.logger.warning(
                "Authentication failed for adapter, skipping.",
                adapter=adapter.source_name,
                error=str(e),
            )
            error_message = str(e)
            is_success = False
        except Exception as e:
            self.logger.error(
                "Critical failure during fetch from adapter.",
                adapter=adapter.source_name,
                error=str(e),
                exc_info=True,
            )
            error_message = str(e)
            races = [
                Race(
                    id=f"error_{adapter.source_name.lower()}",
                    venue=adapter.source_name,
                    race_number=0,
                    start_time=datetime.now(),
                    runners=[],
                    source=adapter.source_name,
                    is_error_placeholder=True,
                    error_message=error_message,
                )
            ]

        duration = (datetime.now() - start_time).total_seconds()

        # Update health monitor
        await self.health_monitor.update_adapter_status(
            adapter_name=adapter.source_name,
            success=is_success,
            latency_ms=duration * 1000,
            error=error_message,
        )

        payload = {
            "races": races,
            "source_info": {
                "name": adapter.source_name,
                "status": "SUCCESS" if is_success else "FAILED",
                "races_fetched": len(races),
                "error_message": error_message,
                "fetch_duration": duration,
                "attempted_url": adapter.attempted_url or attempted_url,
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

                # Maintain source as string
                sources = set(existing_race.source.split(", "))
                sources.add(race.source)
                existing_race.source = ", ".join(sorted(list(sources)))

        return list(race_map.values())

    def _calculate_coverage(self, results: List[Dict[str, Any]]) -> float:
        # Stub implementation
        return 0.0

    def _merge_adapter_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        source_infos = []
        all_races = []
        errors = []

        for adapter_result in results:
            source_info = adapter_result.get("source_info", {})
            source_infos.append(source_info)
            if source_info.get("status") == "SUCCESS":
                all_races.extend(adapter_result.get("races", []))
            else:
                errors.append({
                    "adapter_name": source_info.get("name"),
                    "error_message": source_info.get("error_message", "Unknown error"),
                    "attempted_url": source_info.get("attempted_url")
                })

        deduped_races = self._dedupe_races(all_races)

        return {
            "races": deduped_races,
            "errors": errors,
            "source_info": source_infos
        }

    async def _broadcast_update(self, data: Dict[str, Any]):
        """Helper to broadcast data if the connection manager is available."""
        if self.connection_manager:
            await self.connection_manager.broadcast(data)

    async def fetch_all_odds(self, date: str, source_filter: str = None, min_required_adapters: int = 2) -> Dict[str, Any]:
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Re-introduce live caching
        cache_key = f"fortuna_engine_races:{date}:{source_filter or 'all'}"
        cached_data = await self.get_from_cache(cache_key)
        if cached_data:
            log.info("Cache hit for fetch_all_odds", key=cache_key)
            return json.loads(cached_data)

        all_payloads = []
        attempted_adapters = []
        all_adapter_names = list(self.adapters.keys())
        if source_filter:
            all_adapter_names = [name for name in all_adapter_names if name.lower() == source_filter.lower()]

        ordered_adapter_names = self.health_monitor.get_ordered_adapters(all_adapter_names)

        # Tier 1: Healthy
        healthy_names = [name for name in ordered_adapter_names if self.health_monitor.statuses[name].health == AdapterHealth.HEALTHY]
        if healthy_names:
            tasks = [self._fetch_with_semaphore(self.adapters[name], date) for name in healthy_names]
            attempted_adapters.extend(healthy_names)
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in results:
                if not isinstance(res, Exception):
                    _adapter_name, payload, _duration = res
                    all_payloads.append(payload)

        successful_count = len([p for p in all_payloads if p['source_info']['status'] == 'SUCCESS'])

        # Tier 2: Degraded
        if successful_count < min_required_adapters:
            degraded_names = [name for name in ordered_adapter_names if self.health_monitor.statuses[name].health == AdapterHealth.DEGRADED]
            if degraded_names:
                tasks = [self._fetch_with_semaphore(self.adapters[name], date) for name in degraded_names]
                attempted_adapters.extend(degraded_names)
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for res in results:
                    if not isinstance(res, Exception):
                        _adapter_name, payload, _duration = res
                        all_payloads.append(payload)

        # Tier 3: Stale cache fallback
        if not any(p['source_info']['status'] == 'SUCCESS' for p in all_payloads):
            log.warning("All live adapters failed, attempting to use stale cache.")
            stale_data = await self.stale_data_cache.get(date)
            if stale_data:
                log.info("Using stale data from cache.", cache_age_hours=stale_data['age_hours'])
                stale_results = stale_data['data']
                if 'metadata' in stale_results:
                    stale_results['metadata']['data_freshness'] = 'stale'
                stale_results['warnings'] = ["Using cached data from a previous run as all live sources failed."]
                return stale_results

        if not all_payloads:
            log.error("All adapter fetches failed and no stale data available.")
            return {"races": [], "errors": [{"adapter_name": "all", "error_message": "All adapters failed and no stale data available."}], "source_info": [], "metadata": {}}

        merged_results = self._merge_adapter_results(all_payloads)
        successful_count = len([s for s in merged_results["source_info"] if s["status"] == "SUCCESS"])

        try:
            parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            parsed_date = datetime.now().date()

        response_obj = AggregatedResponse(
            date=parsed_date,
            races=merged_results["races"],
            errors=merged_results["errors"],
            source_info=merged_results["source_info"],
            metadata={
                "fetch_time": datetime.now(),
                "sources_queried": attempted_adapters,
                "sources_successful": successful_count,
                "total_races": len(merged_results["races"]),
                "total_errors": len(merged_results["errors"]),
                'coverage': self._calculate_coverage(all_payloads),
                'data_freshness': 'live'
            },
        )
        response_data = response_obj.model_dump(by_alias=True)

        # Cache successful live results
        if successful_count > 0:
            await self.stale_data_cache.set(date, response_data)
            await self.set_in_cache(cache_key, json.dumps(response_data, default=str), ttl=300)

        await self._broadcast_update(response_data)
        return response_data
