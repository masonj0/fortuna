"""
Canary mode for early detection of upstream changes.
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import random

from ..observability import get_logger, metrics, capture_exception
from .adaptive_selector import get_browser_selector, BrowserBackend

logger = get_logger(__name__)


@dataclass
class CanaryResult:
    """Result of a canary check."""
    track: str
    adapter: str
    success: bool
    race_count: int
    runner_count: int
    latency_ms: float
    timestamp: datetime
    error: Optional[str] = None


class CanaryMonitor:
    """
    Runs lightweight canary checks on a subset of tracks.
    Detects upstream site changes before full report runs.
    """

    def __init__(
        self,
        check_interval: timedelta = timedelta(minutes=30),
        sample_size: int = 3,  # Number of tracks to check
    ):
        self.check_interval = check_interval
        self.sample_size = sample_size

        self._last_check: Optional[datetime] = None
        self._results: List[CanaryResult] = []
        self._known_tracks: Set[str] = set()
        self._baseline: Dict[str, Dict] = {}  # track -> expected metrics

    async def should_run(self) -> bool:
        """Check if canary should run based on interval."""
        if self._last_check is None:
            return True
        return datetime.utcnow() - self._last_check > self.check_interval

    async def run_canary_check(
        self,
        adapters: List[Any],  # BaseAdapterV3 instances
        tracks: Optional[List[str]] = None,
    ) -> List[CanaryResult]:
        """
        Run canary checks on a sample of tracks.

        Args:
            adapters: List of adapter instances to test
            tracks: Specific tracks to check, or None for random sample
        """
        results = []
        self._last_check = datetime.utcnow()

        # Select tracks to check
        if tracks:
            sample_tracks = tracks[:self.sample_size]
        elif self._known_tracks:
            sample_tracks = random.sample(
                list(self._known_tracks),
                min(self.sample_size, len(self._known_tracks))
            )
        else:
            # No known tracks yet, just run adapters
            sample_tracks = ["default"]

        logger.info(f"Running canary check", tracks=sample_tracks)

        for adapter in adapters:
            for track in sample_tracks:
                try:
                    result = await self._check_single(adapter, track)
                    results.append(result)

                    # Update baseline
                    if result.success:
                        self._update_baseline(result)

                    # Check for anomalies
                    anomalies = self._detect_anomalies(result)
                    if anomalies:
                        logger.warning(
                            f"Canary anomalies detected",
                            track=track,
                            adapter=adapter.SOURCE_NAME,
                            anomalies=anomalies
                        )
                        metrics.inc("canary_anomalies", labels={
                            "adapter": adapter.SOURCE_NAME,
                            "track": track
                        })

                except Exception as e:
                    logger.error(f"Canary check failed: {e}")
                    capture_exception(e, tags={"component": "canary", "track": track})
                    results.append(CanaryResult(
                        track=track,
                        adapter=adapter.SOURCE_NAME,
                        success=False,
                        race_count=0,
                        runner_count=0,
                        latency_ms=0,
                        timestamp=datetime.utcnow(),
                        error=str(e)
                    ))

        self._results.extend(results)

        # Emit metrics
        success_count = sum(1 for r in results if r.success)
        metrics.set("canary_success_rate", success_count / len(results) if results else 0)

        return results

    async def _check_single(self, adapter, track: str) -> CanaryResult:
        """Run a single canary check."""
        import time
        start = time.perf_counter()

        # Fetch today's date
        date = datetime.utcnow().strftime("%Y-%m-%d")

        try:
            # Use adapter's fetch method
            races = await adapter.get_races(date)

            latency = (time.perf_counter() - start) * 1000

            # Count totals
            race_count = len(races) if races else 0
            runner_count = sum(len(r.runners) for r in races) if races else 0

            # Track known tracks
            for race in (races or []):
                self._known_tracks.add(race.venue)

            return CanaryResult(
                track=track,
                adapter=adapter.SOURCE_NAME,
                success=True,
                race_count=race_count,
                runner_count=runner_count,
                latency_ms=latency,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return CanaryResult(
                track=track,
                adapter=adapter.SOURCE_NAME,
                success=False,
                race_count=0,
                runner_count=0,
                latency_ms=latency,
                timestamp=datetime.utcnow(),
                error=str(e)
            )

    def _update_baseline(self, result: CanaryResult):
        """Update baseline metrics for track."""
        key = f"{result.adapter}:{result.track}"

        if key not in self._baseline:
            self._baseline[key] = {
                "avg_race_count": result.race_count,
                "avg_runner_count": result.runner_count,
                "avg_latency_ms": result.latency_ms,
                "sample_count": 1,
            }
        else:
            baseline = self._baseline[key]
            n = baseline["sample_count"]

            # Running average
            baseline["avg_race_count"] = (baseline["avg_race_count"] * n + result.race_count) / (n + 1)
            baseline["avg_runner_count"] = (baseline["avg_runner_count"] * n + result.runner_count) / (n + 1)
            baseline["avg_latency_ms"] = (baseline["avg_latency_ms"] * n + result.latency_ms) / (n + 1)
            baseline["sample_count"] = n + 1

    def _detect_anomalies(self, result: CanaryResult) -> List[str]:
        """Detect anomalies compared to baseline."""
        anomalies = []
        key = f"{result.adapter}:{result.track}"

        if key not in self._baseline or self._baseline[key]["sample_count"] < 3:
            return []  # Not enough data

        baseline = self._baseline[key]

        # Check race count
        if result.race_count == 0 and baseline["avg_race_count"] > 0:
            anomalies.append("zero_races")
        elif baseline["avg_race_count"] > 0:
            ratio = result.race_count / baseline["avg_race_count"]
            if ratio < 0.5:
                anomalies.append(f"low_race_count:{ratio:.2f}x")
            elif ratio > 2.0:
                anomalies.append(f"high_race_count:{ratio:.2f}x")

        # Check latency
        if baseline["avg_latency_ms"] > 0:
            ratio = result.latency_ms / baseline["avg_latency_ms"]
            if ratio > 3.0:
                anomalies.append(f"high_latency:{ratio:.2f}x")

        return anomalies

    def get_health_summary(self) -> Dict:
        """Get canary health summary."""
        recent = [r for r in self._results[-50:]]  # Last 50 results

        if not recent:
            return {"status": "unknown", "message": "No canary data"}

        success_rate = sum(1 for r in recent if r.success) / len(recent)

        if success_rate >= 0.9:
            status = "healthy"
        elif success_rate >= 0.7:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "success_rate": f"{success_rate:.2%}",
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "recent_results": len(recent),
            "known_tracks": len(self._known_tracks),
        }
