# python_service/engine.py

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple

import httpx
import structlog

from .adapters.base_v3 import BaseAdapterV3 # Import V3 base class
from .adapters import * # Import all adapter classes
from .core.exceptions import AdapterConfigError, AdapterHttpError
from .cache_manager import cache_async_result
from .config import get_settings
from .models import AggregatedResponse, Race, Runner

log = structlog.get_logger(__name__)


class OddsEngine:
    def __init__(self, config=None):
        self.logger = structlog.get_logger(__name__)
        self.logger.info("Initializing FortunaEngine...")

        try:
            self.config = config or get_settings()
            self.logger.info("Configuration loaded.")

            self.logger.info("Initializing adapters...")
            self.adapters: List[BaseAdapterV3] = []
            adapter_classes = [
                AtTheRacesAdapter, BetfairAdapter, BetfairGreyhoundAdapter, BrisnetAdapter,
                DRFAdapter, EquibaseAdapter, FanDuelAdapter, GbgbApiAdapter, GreyhoundAdapter,
                HarnessAdapter, HorseRacingNationAdapter, NYRABetsAdapter, OddscheckerAdapter,
                PuntersAdapter, RacingAndSportsAdapter, RacingAndSportsGreyhoundAdapter,
                RacingPostAdapter, RacingTVAdapter, SportingLifeAdapter, TabAdapter,
                TheRacingApiAdapter, TimeformAdapter, TwinSpiresAdapter, TVGAdapter,
                XpressbetAdapter, PointsBetGreyhoundAdapter
            ]

            for adapter_cls in adapter_classes:
                try:
                    self.adapters.append(adapter_cls(config=self.config))
                except AdapterConfigError as e:
                    self.logger.warning(
                        "Skipping adapter due to configuration error",
                        adapter=adapter_cls.__name__,
                        error=str(e)
                    )
                except Exception:
                    self.logger.error(f"An unexpected error occurred while initializing {adapter_cls.__name__}", exc_info=True)

            # Special case for BetfairDataScientistAdapter with extra args
            try:
                self.adapters.append(BetfairDataScientistAdapter(
                    model_name="ThoroughbredModel",
                    url="https://betfair-data-supplier-prod.herokuapp.com/api/widgets/kvs-ratings/datasets",
                    config=self.config
                ))
            except Exception:
                self.logger.warning("Failed to initialize adapter: BetfairDataScientistAdapter", exc_info=True)

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
            self.logger.info("Concurrency semaphore initialized", limit=self.config.MAX_CONCURRENT_REQUESTS)

            self.logger.info("FortunaEngine initialization complete.")

        except Exception:
            self.logger.critical("CRITICAL FAILURE during FortunaEngine initialization.", exc_info=True)
            raise

    async def close(self):
        await self.http_client.aclose()

    def get_all_adapter_statuses(self) -> List[Dict[str, Any]]:
        return [adapter.get_status() for adapter in self.adapters]

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
        payload = {}

        try:
            payload = await adapter.get_races(date)
            races = payload.get("races", [])
            is_success = True
        except AdapterHttpError as e:
            self.logger.error(
                "HTTP failure during fetch from adapter.",
                adapter=adapter.source_name,
                status_code=e.status_code,
                url=e.url,
                exc_info=False
            )
            error_message = f"HTTP Error {e.status_code} for {e.url}"
            attempted_url = e.url
        except Exception as e:
            self.logger.error(
                "Critical failure during fetch from adapter.",
                adapter=adapter.source_name,
                error=str(e),
                exc_info=True
            )
            error_message = str(e)

        duration = (datetime.now() - start_time).total_seconds()

        final_payload = {
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
        return (adapter.source_name, final_payload, duration)

    def _race_key(self, race: Race) -> str:
        return f"{race.venue.lower().strip()}|{race.race_number}|{race.start_time.strftime('%H:%M')}"

    def _dedupe_races(self, races: List[Race]) -> List[Race]:
        """Deduplicates races and reconciles odds from different sources."""
        race_map: Dict[str, Race] = {}
        for race in races:
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

    @cache_async_result(ttl_seconds=300, key_prefix="fortuna_engine_races")
    async def fetch_all_odds(self, date: str, source_filter: str = None) -> Dict[str, Any]:
        """
        Fetches and aggregates race data from all configured adapters.
        The result of this method is cached.
        """
        target_adapters = self.adapters
        if source_filter:
            log.info("Applying source filter", source=source_filter)
            target_adapters = [a for a in self.adapters if a.source_name.lower() == source_filter.lower()]

        tasks = [self._fetch_with_semaphore(adapter, date) for adapter in target_adapters]
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
                "sources_successful": len([s for s in source_infos if s["status"] == "SUCCESS"]),
                "total_races": len(deduped_races),
            },
        )
        return response_obj.model_dump(by_alias=True)
