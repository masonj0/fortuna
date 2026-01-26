"""
Parallel fetching orchestrator for running adapters concurrently.
"""

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import time

from ..observability import get_logger, metrics, capture_exception
from ..quality.anomaly_detector import AnomalyDetector

logger = get_logger(__name__)


class FetchStatus(Enum):
    """Status of a fetch operation."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class FetchResult:
    """Result of a single adapter fetch."""
    adapter_name: str
    status: FetchStatus
    races: List[Any] = field(default_factory=list)
    race_count: int = 0
    duration_ms: float = 0.0
    error: Optional[str] = None
    anomalies: List[Any] = field(default_factory=list)
    retries: int = 0


@dataclass
class AggregatedResult:
    """Aggregated result from all adapters."""
    all_races: List[Any]
    adapter_results: List[FetchResult]
    total_duration_ms: float
    success_count: int
    failure_count: int
    total_race_count: int
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ParallelFetcher:
    """
    Orchestrates parallel fetching from multiple adapters.

    Features:
    - Concurrent execution with semaphore control
    - Per-adapter timeout handling
    - Result aggregation and deduplication
    - Anomaly detection integration
    """

    def __init__(
        self,
        adapters: List[Any],
        max_concurrent: int = 5,
        adapter_timeout: float = 60.0,
        enable_anomaly_detection: bool = True,
    ):
        self.adapters = adapters
        self.max_concurrent = max_concurrent
        self.adapter_timeout = adapter_timeout
        self.enable_anomaly_detection = enable_anomaly_detection

        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._anomaly_detector = AnomalyDetector() if enable_anomaly_detection else None

    async def fetch_all(
        self,
        date: str,
        required_adapters: Optional[List[str]] = None,
    ) -> AggregatedResult:
        """
        Fetch races from all adapters in parallel.

        Args:
            date: Date string in YYYY-MM-DD format
            required_adapters: Optional list of adapter names that must succeed

        Returns:
            AggregatedResult with all races and per-adapter stats
        """
        start_time = time.perf_counter()
        logger.info(f"Starting parallel fetch", date=date, adapters=len(self.adapters))

        # Create tasks for all adapters
        tasks = [
            self._fetch_with_semaphore(adapter, date)
            for adapter in self.adapters
        ]

        # Execute all tasks
        results: List[FetchResult] = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        processed_results = []
        all_races = []

        for i, result in enumerate(results):
            adapter_name = self.adapters[i].SOURCE_NAME

            if isinstance(result, Exception):
                # Task raised an exception
                capture_exception(result, tags={"adapter": adapter_name})
                processed_results.append(FetchResult(
                    adapter_name=adapter_name,
                    status=FetchStatus.FAILED,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
                if result.status in (FetchStatus.SUCCESS, FetchStatus.PARTIAL):
                    all_races.extend(result.races)

        # Deduplicate races
        unique_races = self._deduplicate_races(all_races)

        # Calculate stats
        total_duration = (time.perf_counter() - start_time) * 1000
        success_count = sum(1 for r in processed_results if r.status == FetchStatus.SUCCESS)
        failure_count = sum(1 for r in processed_results if r.status == FetchStatus.FAILED)

        # Check required adapters
        if required_adapters:
            failed_required = [
                r.adapter_name for r in processed_results
                if r.adapter_name in required_adapters and r.status == FetchStatus.FAILED
            ]
            if failed_required:
                logger.warning(f"Required adapters failed", adapters=failed_required)

        # Emit metrics
        metrics.set("fetch_total_races", len(unique_races))
        metrics.set("fetch_adapter_success_count", success_count)
        metrics.set("fetch_adapter_failure_count", failure_count)
        metrics.observe("fetch_total_duration_seconds", total_duration / 1000)

        logger.info(
            f"Parallel fetch complete",
            total_races=len(unique_races),
            success=success_count,
            failed=failure_count,
            duration_ms=f"{total_duration:.0f}"
        )

        return AggregatedResult(
            all_races=unique_races,
            adapter_results=processed_results,
            total_duration_ms=total_duration,
            success_count=success_count,
            failure_count=failure_count,
            total_race_count=len(unique_races),
        )

    async def _fetch_with_semaphore(
        self,
        adapter,
        date: str,
    ) -> FetchResult:
        """Fetch from a single adapter with concurrency control."""
        async with self._semaphore:
            return await self._fetch_single(adapter, date)

    async def _fetch_single(
        self,
        adapter,
        date: str,
    ) -> FetchResult:
        """Fetch from a single adapter with timeout."""
        adapter_name = adapter.SOURCE_NAME
        start_time = time.perf_counter()

        logger.debug(f"Starting fetch", adapter=adapter_name)

        try:
            # Fetch with timeout
            races = await asyncio.wait_for(
                adapter.get_races(date),
                timeout=self.adapter_timeout
            )

            duration = (time.perf_counter() - start_time) * 1000

            # Run anomaly detection
            anomalies = []
            if self._anomaly_detector and races:
                anomalies, _ = self._anomaly_detector.analyze_races(races, adapter_name)

            # Determine status
            if races is None:
                status = FetchStatus.FAILED
            elif len(races) == 0:
                status = FetchStatus.PARTIAL
            else:
                status = FetchStatus.SUCCESS

            logger.info(
                f"Fetch complete",
                adapter=adapter_name,
                races=len(races) if races else 0,
                duration_ms=f"{duration:.0f}",
                anomalies=len(anomalies)
            )

            return FetchResult(
                adapter_name=adapter_name,
                status=status,
                races=races or [],
                race_count=len(races) if races else 0,
                duration_ms=duration,
                anomalies=anomalies,
            )

        except asyncio.TimeoutError:
            duration = (time.perf_counter() - start_time) * 1000
            logger.warning(f"Fetch timeout", adapter=adapter_name, timeout=self.adapter_timeout)

            return FetchResult(
                adapter_name=adapter_name,
                status=FetchStatus.TIMEOUT,
                duration_ms=duration,
                error=f"Timeout after {self.adapter_timeout}s"
            )

        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000
            logger.error(f"Fetch error", adapter=adapter_name, error=str(e), exc_info=True)
            capture_exception(e, tags={"adapter": adapter_name})

            return FetchResult(
                adapter_name=adapter_name,
                status=FetchStatus.FAILED,
                duration_ms=duration,
                error=str(e)
            )

    def _deduplicate_races(self, races: List[Any]) -> List[Any]:
        """
        Deduplicate races across adapters.
        Prefer races with more complete data.
        """
        seen = {}  # race_key -> race

        for race in races:
            key = self._make_race_key(race)

            if key not in seen:
                seen[key] = race
            else:
                # Keep the one with more runners
                existing = seen[key]
                existing_runners = len(existing.runners) if hasattr(existing, 'runners') else 0
                new_runners = len(race.runners) if hasattr(race, 'runners') else 0

                if new_runners > existing_runners:
                    seen[key] = race

        return list(seen.values())

    def _make_race_key(self, race) -> str:
        """Generate a unique key for a race."""
        venue = (race.venue if hasattr(race, 'venue') else "unknown").lower()
        venue = ''.join(c for c in venue if c.isalnum())

        race_num = race.race_number if hasattr(race, 'race_number') else 0

        # Include date if available from start_time
        date_str = ""
        if hasattr(race, 'start_time') and race.start_time:
            date_str = race.start_time.strftime("%Y%m%d")

        return f"{venue}_{date_str}_R{race_num}"
