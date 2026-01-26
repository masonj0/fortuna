"""
Adaptive browser selection based on success rates.
Implements automatic rotation and canary testing.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import random

from ..observability import get_logger, metrics

logger = get_logger(__name__)


class BrowserBackend(Enum):
    """Available browser backends."""
    STEALTHY_CAMOUFOX = "stealthy_camoufox"
    PLAYWRIGHT_CHROMIUM = "playwright_chromium"
    PLAYWRIGHT_FIREFOX = "playwright_firefox"


@dataclass
class BackendStats:
    """Statistics for a browser backend."""
    backend: str
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_latency_ms: float = 0.0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    consecutive_failures: int = 0
    is_available: bool = True
    cooldown_until: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.5  # No data, assume neutral
        return self.successful_attempts / self.total_attempts

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_attempts == 0:
            return float('inf')
        return self.total_latency_ms / self.successful_attempts

    @property
    def score(self) -> float:
        """
        Calculate a score for backend selection.
        Higher is better.
        """
        if not self.is_available:
            return -1000

        if self.cooldown_until and datetime.utcnow() < self.cooldown_until:
            return -500

        # Weighted score: success rate matters most
        success_score = self.success_rate * 100

        # Penalty for recent failures
        recency_penalty = 0
        if self.last_failure:
            minutes_since_failure = (datetime.utcnow() - self.last_failure).total_seconds() / 60
            if minutes_since_failure < 10:
                recency_penalty = 20 * (1 - minutes_since_failure / 10)

        # Latency bonus (faster is better, but capped)
        latency_bonus = max(0, 10 - self.avg_latency_ms / 1000)

        return success_score - recency_penalty + latency_bonus - (self.consecutive_failures * 5)


class AdaptiveBrowserSelector:
    """
    Selects the best browser backend based on historical performance.
    """

    # Thresholds
    COOLDOWN_THRESHOLD = 3  # Consecutive failures before cooldown
    COOLDOWN_DURATION = timedelta(minutes=15)
    MIN_SAMPLE_SIZE = 5  # Minimum attempts before trusting stats
    EXPLORATION_RATE = 0.1  # 10% chance to try non-optimal backend

    def __init__(
        self,
        state_path: Optional[Path] = None,
        available_backends: Optional[List[BrowserBackend]] = None,
    ):
        self.state_path = state_path or Path("browser_selector_state.json")
        self.available_backends = available_backends or list(BrowserBackend)

        self._stats: Dict[str, BackendStats] = {}
        self._lock = asyncio.Lock()

        # Initialize stats for each backend
        for backend in self.available_backends:
            self._stats[backend.value] = BackendStats(backend=backend.value)

        # Load persisted state
        self._load_state()

    def _load_state(self):
        """Load persisted state from file."""
        try:
            if self.state_path.exists():
                with open(self.state_path) as f:
                    data = json.load(f)

                for backend_name, stats_data in data.get("stats", {}).items():
                    if backend_name in self._stats:
                        # Update stats from persisted data
                        stats = self._stats[backend_name]
                        stats.total_attempts = stats_data.get("total_attempts", 0)
                        stats.successful_attempts = stats_data.get("successful_attempts", 0)
                        stats.failed_attempts = stats_data.get("failed_attempts", 0)
                        stats.total_latency_ms = stats_data.get("total_latency_ms", 0.0)
                        stats.is_available = stats_data.get("is_available", True)

                        if stats_data.get("last_success"):
                            stats.last_success = datetime.fromisoformat(stats_data["last_success"])
                        if stats_data.get("last_failure"):
                            stats.last_failure = datetime.fromisoformat(stats_data["last_failure"])

                logger.info("Loaded browser selector state", backends=len(self._stats))
        except Exception as e:
            logger.warning(f"Failed to load browser selector state: {e}")

    def _save_state(self):
        """Persist state to file."""
        try:
            data = {
                "updated_at": datetime.utcnow().isoformat(),
                "stats": {
                    name: {
                        "total_attempts": s.total_attempts,
                        "successful_attempts": s.successful_attempts,
                        "failed_attempts": s.failed_attempts,
                        "total_latency_ms": s.total_latency_ms,
                        "is_available": s.is_available,
                        "last_success": s.last_success.isoformat() if s.last_success else None,
                        "last_failure": s.last_failure.isoformat() if s.last_failure else None,
                    }
                    for name, s in self._stats.items()
                }
            }

            with open(self.state_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save browser selector state: {e}")

    async def select_backend(
        self,
        exclude: Optional[List[BrowserBackend]] = None,
        prefer: Optional[BrowserBackend] = None,
    ) -> BrowserBackend:
        """
        Select the best browser backend based on current stats.

        Uses epsilon-greedy exploration: mostly picks the best,
        but occasionally tries others to gather data.
        """
        async with self._lock:
            exclude_set = {b.value for b in (exclude or [])}

            # Get available backends with their scores
            candidates = []
            for backend in self.available_backends:
                if backend.value in exclude_set:
                    continue

                stats = self._stats[backend.value]

                # Skip if in cooldown
                if stats.cooldown_until and datetime.utcnow() < stats.cooldown_until:
                    continue

                if not stats.is_available:
                    continue

                candidates.append((backend, stats.score))

            if not candidates:
                # All backends unavailable, reset cooldowns and try again
                logger.warning("All backends in cooldown, resetting...")
                for stats in self._stats.values():
                    stats.cooldown_until = None
                    stats.consecutive_failures = 0
                return self.available_backends[0]

            # Sort by score (descending)
            candidates.sort(key=lambda x: x[1], reverse=True)

            # Epsilon-greedy exploration
            if random.random() < self.EXPLORATION_RATE and len(candidates) > 1:
                # Pick a random non-optimal backend
                selected = random.choice(candidates[1:])[0]
                logger.debug(f"Exploration: selected {selected.value}")
            else:
                selected = candidates[0][0]

            # Override with preference if provided and viable
            if prefer and prefer.value not in exclude_set:
                prefer_stats = self._stats[prefer.value]
                if prefer_stats.is_available and not (
                    prefer_stats.cooldown_until and datetime.utcnow() < prefer_stats.cooldown_until
                ):
                    selected = prefer

            logger.info(
                f"Selected browser backend",
                backend=selected.value,
                score=self._stats[selected.value].score,
                success_rate=f"{self._stats[selected.value].success_rate:.2%}"
            )

            return selected

    async def record_result(
        self,
        backend: BrowserBackend,
        success: bool,
        latency_ms: float = 0.0,
        error_type: Optional[str] = None,
    ):
        """Record the result of a fetch attempt."""
        async with self._lock:
            stats = self._stats[backend.value]
            stats.total_attempts += 1

            if success:
                stats.successful_attempts += 1
                stats.total_latency_ms += latency_ms
                stats.last_success = datetime.utcnow()
                stats.consecutive_failures = 0

                # Clear cooldown on success
                stats.cooldown_until = None

                metrics.inc("browser_fetch_success", labels={"backend": backend.value})
            else:
                stats.failed_attempts += 1
                stats.last_failure = datetime.utcnow()
                stats.consecutive_failures += 1

                metrics.inc("browser_fetch_failure", labels={
                    "backend": backend.value,
                    "error_type": error_type or "unknown"
                })

                # Apply cooldown if too many consecutive failures
                if stats.consecutive_failures >= self.COOLDOWN_THRESHOLD:
                    stats.cooldown_until = datetime.utcnow() + self.COOLDOWN_DURATION
                    logger.warning(
                        f"Backend entering cooldown",
                        backend=backend.value,
                        consecutive_failures=stats.consecutive_failures,
                        cooldown_until=stats.cooldown_until.isoformat()
                    )

            # Record latency histogram
            if latency_ms > 0:
                metrics.observe(
                    "browser_fetch_latency_seconds",
                    latency_ms / 1000,
                    labels={"backend": backend.value}
                )

            # Persist state
            self._save_state()

    def set_backend_availability(self, backend: BrowserBackend, available: bool):
        """Set whether a backend is available."""
        self._stats[backend.value].is_available = available
        self._save_state()

    def get_stats_summary(self) -> Dict[str, Any]:
        """Get a summary of all backend stats."""
        return {
            name: {
                "success_rate": f"{s.success_rate:.2%}",
                "avg_latency_ms": f"{s.avg_latency_ms:.0f}",
                "total_attempts": s.total_attempts,
                "consecutive_failures": s.consecutive_failures,
                "score": f"{s.score:.1f}",
                "is_available": s.is_available,
                "in_cooldown": bool(s.cooldown_until and datetime.utcnow() < s.cooldown_until),
            }
            for name, s in self._stats.items()
        }


# Global instance
_browser_selector: Optional[AdaptiveBrowserSelector] = None


def get_browser_selector() -> AdaptiveBrowserSelector:
    """Get the global browser selector instance."""
    global _browser_selector
    if _browser_selector is None:
        _browser_selector = AdaptiveBrowserSelector()
    return _browser_selector
