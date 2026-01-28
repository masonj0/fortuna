# python_service/adapters/base_v3.py
from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

import httpx
import structlog
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from python_service.core.smart_fetcher import (
    BrowserEngine,
    FetchStrategy,
    SmartFetcher,
    StealthMode,
)

from ..core.exceptions import AdapterHttpError, AdapterParsingError, ErrorCategory
from ..manual_override_manager import ManualOverrideManager
from ..models import Race
from ..validators import DataValidationPipeline

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Thread-safe circuit breaker implementation."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3

    _failure_count: int = field(default=0, repr=False)
    _last_failure_time: float = field(default=0.0, repr=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    _half_open_calls: int = field(default=0, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    @property
    def state(self) -> CircuitState:
        """Returns current state without mutation. Use check_state() for transitions."""
        return self._state

    async def check_and_transition_state(self) -> CircuitState:
        """Check state and handle OPEN -> HALF_OPEN transition atomically."""
        async with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
            return self._state

    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED

    async def record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
            elif self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN

    async def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        state = await self.check_and_transition_state()
        return state in (CircuitState.CLOSED, CircuitState.HALF_OPEN)


@dataclass
class RateLimiter:
    """Token bucket rate limiter."""
    requests_per_second: float = 10.0
    burst_size: int = 20

    _tokens: float = field(default=0.0, init=False, repr=False)
    _last_update: float = field(default=0.0, init=False, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self._tokens = float(self.burst_size)
        self._last_update = time.monotonic()

    async def acquire(self) -> None:
        """Acquire a token, waiting if necessary."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_update
            self._tokens = min(self.burst_size, self._tokens + elapsed * self.requests_per_second)
            self._last_update = now

            if self._tokens < 1:
                wait_time = (1 - self._tokens) / self.requests_per_second
                await asyncio.sleep(wait_time)
                self._tokens = 0
            else:
                self._tokens -= 1


@dataclass
class CacheEntry:
    """Cache entry with TTL."""
    data: Any
    created_at: float
    ttl: float

    @property
    def is_expired(self) -> bool:
        return time.monotonic() - self.created_at > self.ttl


class ResponseCache:
    """Simple in-memory response cache."""

    def __init__(self, default_ttl: float = 300.0, max_entries: int = 1000):
        self.default_ttl = default_ttl
        self.max_entries = max_entries
        self._cache: dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _make_key(method: str, url: str, **kwargs) -> str:
        """Generate a stable cache key from request parameters."""
        # Filter out non-hashable or irrelevant kwargs
        cacheable_kwargs = {
            k: v for k, v in kwargs.items()
            if k not in ('headers', 'timeout', 'follow_redirects')
            and isinstance(v, (str, int, float, bool, tuple, type(None)))
        }
        key_data = f"{method}:{url}:{json.dumps(cacheable_kwargs, sort_keys=True, default=str)}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    async def get(self, method: str, url: str, **kwargs) -> Any | None:
        """Get a cached response if available and not expired."""
        key = self._make_key(method, url, **kwargs)

        async with self._lock:
            entry = self._cache.get(key)
            if entry and not entry.is_expired:
                return entry.data
            elif entry:
                del self._cache[key]
        return None

    async def set(self, method: str, url: str, data: Any, ttl: float | None = None, **kwargs) -> None:
        """Cache a response."""
        key = self._make_key(method, url, **kwargs)

        async with self._lock:
            # Evict old entries if cache is full
            if len(self._cache) >= self.max_entries:
                expired_keys = [k for k, v in self._cache.items() if v.is_expired]
                for k in expired_keys:
                    del self._cache[k]

                # If still full, remove oldest entries
                if len(self._cache) >= self.max_entries:
                    oldest = sorted(self._cache.items(), key=lambda x: x[1].created_at)
                    for k, _ in oldest[:len(self._cache) // 4]:
                        del self._cache[k]

            self._cache[key] = CacheEntry(
                data=data,
                created_at=time.monotonic(),
                ttl=ttl or self.default_ttl
            )

    async def clear(self) -> None:
        """Clear all cached entries."""
        async with self._lock:
            self._cache.clear()


@dataclass
class AdapterMetrics:
    """Thread-safe metrics for adapter health monitoring."""
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _total_requests: int = field(default=0, repr=False)
    _successful_requests: int = field(default=0, repr=False)
    _failed_requests: int = field(default=0, repr=False)
    _total_latency_ms: float = field(default=0.0, repr=False)
    _last_success: float | None = field(default=None, repr=False)
    _last_failure: float | None = field(default=None, repr=False)
    _last_error: str | None = field(default=None, repr=False)

    @property
    def total_requests(self) -> int:
        return self._total_requests

    @property
    def success_rate(self) -> float:
        if self._total_requests == 0:
            return 1.0
        return self._successful_requests / self._total_requests

    @property
    def avg_latency_ms(self) -> float:
        if self._successful_requests == 0:
            return 0.0
        return self._total_latency_ms / self._successful_requests

    async def record_success(self, latency_ms: float) -> None:
        async with self._lock:
            self._total_requests += 1
            self._successful_requests += 1
            self._total_latency_ms += latency_ms
            self._last_success = time.time()

    async def record_failure(self, error: str) -> None:
        async with self._lock:
            self._total_requests += 1
            self._failed_requests += 1
            self._last_failure = time.time()
            self._last_error = error

    @property
    def consecutive_failures(self) -> int:
        # This is a bit tricky with the current lock-only metrics,
        # but we can track it if we add a field.
        return getattr(self, "_consecutive_failures", 0)

    def snapshot(self) -> dict[str, Any]:
        """Return a point-in-time snapshot of metrics."""
        return {
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "success_rate": self.success_rate,
            "avg_latency_ms": self.avg_latency_ms,
            "last_success": self._last_success,
            "last_failure": self._last_failure,
            "last_error": self._last_error,
        }


class BaseAdapterV3(ABC):
    """
    Abstract base class for all V3 data adapters.

    Features:
    - Standardized fetch/parse pattern
    - Retry logic with exponential backoff
    - Circuit breaker for fault tolerance
    - Rate limiting
    - Response caching
    - Comprehensive metrics
    """

    # List of common User-Agent strings for rotation
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    ]

    @property
    def DEFAULT_USER_AGENT(self) -> str:
        """Return a randomly selected User-Agent."""
        return random.choice(self.USER_AGENTS)

    def __init__(
        self,
        source_name: str,
        base_url: str,
        config: Any = None,
        timeout: int = 20,
        enable_cache: bool = True,
        cache_ttl: float = 300.0,
        rate_limit: float = 10.0,
    ):
        self.source_name = source_name
        self.base_url = base_url.rstrip("/")
        self.config = config
        self.timeout = timeout
        self.logger = structlog.get_logger(adapter_name=self.source_name)
        self.http_client: httpx.AsyncClient | None = None
        self.manual_override_manager: ManualOverrideManager | None = None
        self.supports_manual_override = True
        self.attempted_url: Optional[str] = None
        self._initial_rate_limit = rate_limit
        # ✅ THESE 4 LINES MUST BE HERE (not in close()):
        self.circuit_breaker = CircuitBreaker()
        self.rate_limiter = RateLimiter(requests_per_second=rate_limit)
        self.cache = ResponseCache(default_ttl=cache_ttl) if enable_cache else None
        self.metrics = AdapterMetrics()

        # New SmartFetcher integration
        self.fetch_strategy = self._configure_fetch_strategy()
        self.smart_fetcher = SmartFetcher(strategy=self.fetch_strategy)

    async def __aenter__(self) -> "BaseAdapterV3":
        """Async context manager entry."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with cleanup."""
        await self.close()

    async def close(self) -> None:
        """Clean up resources, including the SmartFetcher."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
        if hasattr(self, "smart_fetcher"):
            await self.smart_fetcher.close()
        if self.cache:
            await self.cache.clear()
        self.logger.debug("Adapter resources cleaned up")

    def enable_manual_override(self, manager: ManualOverrideManager) -> None:
        """Injects the manual override manager into the adapter."""
        self.manual_override_manager = manager

    @abstractmethod
    async def _fetch_data(self, date: str) -> Any:
        """
        Fetches the raw data (e.g., HTML, JSON) for the given date.
        This is the only method that should perform network operations.
        """
        raise NotImplementedError

    @abstractmethod
    def _parse_races(self, raw_data: Any) -> list[Race]:
        """
        Parses the raw data retrieved by _fetch_data into a list of Race objects.
        This method should be a pure function with no side effects.
        """
        raise NotImplementedError

    async def get_races(self, date: str) -> list[Race]:
        """
        Orchestrates the fetch-then-parse pipeline for the adapter.
        This public method should not be overridden by subclasses.
        """
        raw_data = None

        # Check for manual override data first
        if self.manual_override_manager:
            lookup_key = f"{self.base_url}/racecards/{date}"
            manual_data = self.manual_override_manager.get_manual_data(self.source_name, lookup_key)
            if manual_data:
                self.logger.info("Using manually submitted data", url=lookup_key)
                raw_data = {"pages": [manual_data[0]], "date": date}

        # Fetch from source if no manual data
        if raw_data is None:
            try:
                raw_data = await self._fetch_data(date)
            except AdapterHttpError as e:
                if self.manual_override_manager and self.supports_manual_override:
                    self.manual_override_manager.register_failure(self.source_name, e.url)
                raise

        # Parse the data
        if raw_data is not None:
            return self._validate_and_parse_races(raw_data)

        return []

    def _validate_and_parse_races(self, raw_data: Any) -> list[Race]:
        self.attempted_url = None  # Reset for each new get_races call
        is_valid, reason = DataValidationPipeline.validate_raw_response(self.source_name, raw_data)
        if not is_valid:
            raise AdapterParsingError(self.source_name, f"Raw response validation failed: {reason}")

        try:
            parsed_races = self._parse_races(raw_data)
        except Exception as e:
            self.logger.error("Failed to parse race data", error=str(e), exc_info=True)
            # Save a snapshot of the problematic data on parsing failure
            self._save_debug_snapshot(
                content=str(raw_data),
                context="parsing_error",
                url=getattr(e, 'url', self.attempted_url)
            )
            raise AdapterParsingError(self.source_name, "Parsing logic failed.") from e

        validated_races, warnings = DataValidationPipeline.validate_parsed_races(parsed_races)

        if warnings:
            self.logger.warning("Validation warnings during parsing", warnings=warnings)

        return validated_races

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """
        Defines the fetching strategy for this adapter. Subclasses should override
        this method to customize fetching behavior based on the target website's
        characteristics (e.g., anti-bot measures, JavaScript requirements).

        Example Overrides:
        - SportingLife: Needs JS rendering -> primary_engine=BrowserEngine.PLAYWRIGHT
        - AtTheRaces: Simple HTML -> primary_engine=BrowserEngine.HTTPX
        - RacingPost: Strong anti-bot -> stealth_mode=StealthMode.CAMOUFLAGE
        """
        return FetchStrategy(
            primary_engine=BrowserEngine.PLAYWRIGHT,
            enable_js=True,
            stealth_mode=StealthMode.FAST,
            block_resources=True,
            max_retries=3,
            timeout=30,
        )

    async def _adjust_rate_limit(self, success: bool):
        """Dynamically adjust rate limits based on performance."""
        # Target RPS is what was initially configured
        target_rps = getattr(self, "_initial_rate_limit", 5.0)
        current_rps = self.rate_limiter.requests_per_second

        if not success:
            # On failure, aggressively reduce rate limit (halve it)
            new_rps = max(0.1, current_rps * 0.5)
            if new_rps < current_rps:
                self.rate_limiter.requests_per_second = new_rps
                self.logger.warning("Backing off: reduced rate limit",
                                     new_rps=round(new_rps, 2),
                                     old_rps=round(current_rps, 2))
        else:
            # On success, slowly increase rate limit back to target
            if current_rps < target_rps:
                new_rps = min(target_rps, current_rps + 0.05)
                if new_rps > current_rps:
                    self.rate_limiter.requests_per_second = new_rps
                    self.logger.debug("Scaling up: increased rate limit",
                                      new_rps=round(new_rps, 2))

    async def make_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """
        Performs a web request using the SmartFetcher, which intelligently
        manages browser engines, retries, and stealth capabilities.
        """
        full_url = url if url.startswith("http") else f"{self.base_url}/{url.lstrip('/')}"
        self.attempted_url = full_url

        # Apply rate limiting before the request
        await self.rate_limiter.acquire()

        start_time = time.perf_counter()
        try:
            # The SmartFetcher handles caching, retries, circuit breaking, etc.
            response = await self.smart_fetcher.fetch(full_url, method=method, **kwargs)

            latency_ms = (time.perf_counter() - start_time) * 1000
            await self.metrics.record_success(latency_ms)
            await self.circuit_breaker.record_success()
            await self._adjust_rate_limit(success=True)

            # Log success with rich metadata from the fetcher
            self.logger.info(
                "Request successful",
                url=full_url,
                status=getattr(response, "status", "N/A"),
                size_bytes=len(getattr(response, "text", "")),
                engine=getattr(response, "metadata", {}).get("engine_used", "unknown"),
                latency_ms=round(latency_ms, 1)
            )
            return response

        except Exception as e:
            category = getattr(e, "category", ErrorCategory.UNKNOWN).value
            await self.metrics.record_failure(str(e))
            await self.circuit_breaker.record_failure()
            await self._adjust_rate_limit(success=False)

            # Log failure with detailed diagnostics from the fetcher
            self.logger.error(
                "Request failed after all retries and engine fallbacks",
                url=full_url,
                error=str(e),
                error_type=type(e).__name__,
                error_category=category,
                health_report=self.smart_fetcher.get_health_report(),
            )

            # Save a snapshot if we have a response body in the error
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                self._save_debug_snapshot(
                    content=e.response.text,
                    context=f"request_failed_{getattr(e.response, 'status', 'unknown')}",
                    url=full_url
                )

            # Re-raise as a standard adapter error for consistent downstream handling
            status_code = getattr(getattr(e, 'response', None), 'status', 503)
            raise AdapterHttpError(
                adapter_name=self.source_name, status_code=status_code, url=full_url
            ) from e

    def _should_save_debug_html(self) -> bool:
        """Determines if the current environment is suitable for saving debug files."""
        import os
        return os.getenv("CI") == "true" or os.getenv("DEBUG_MODE") == "true"

    def _save_debug_snapshot(self, content: str, context: str, url: str | None = None):
        """
        Saves HTML or other text content to a file for debugging purposes.
        Enhanced to include metadata and better organization.
        """
        if not self._should_save_debug_html():
            return

        import os
        import re
        import json
        from datetime import datetime

        try:
            debug_dir = os.path.join("debug-snapshots", self.source_name.lower())
            os.makedirs(debug_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")

            # Sanitize context and URL for a safe filename
            sanitized_context = re.sub(r'[\\/*?:"<>|]', "_", context)
            sanitized_url = ""
            if url:
                # Remove protocol and query params for filename
                clean_url = re.sub(r'https?://(www\.)?', '', url).split('?')[0]
                # Avoid backslashes in f-string for Python < 3.12 compatibility
                url_part = re.sub(r'[\\/*?:\x22<>|]', '_', clean_url)[:60]
                sanitized_url = f"_{url_part}"

            base_filename = f"{timestamp}_{sanitized_context}{sanitized_url}"

            # Save the main content (HTML/JSON)
            content_ext = ".json" if content.startswith(("{", "[")) else ".html"
            filepath = os.path.join(debug_dir, f"{base_filename}{content_ext}")

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            # Save metadata for better diagnostic context
            meta_path = os.path.join(debug_dir, f"{base_filename}_meta.json")
            meta = {
                "timestamp": datetime.now().isoformat(),
                "adapter": self.source_name,
                "url": url or self.attempted_url,
                "context": context,
                "engine": getattr(self.smart_fetcher, 'last_engine', 'unknown'),
                "health_report": self.smart_fetcher.get_health_report()
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)

            self.logger.info("Saved debug snapshot and metadata",
                             filepath=filepath, meta_path=meta_path)

            # Prune old snapshots (keep last 50)
            self._prune_debug_snapshots(debug_dir, max_files=100)

        except Exception as e:
            self.logger.warning("Failed to save debug snapshot", error=str(e))

    def _prune_debug_snapshots(self, debug_dir: str, max_files: int = 100):
        """Keep the number of debug files under control."""
        import os
        try:
            files = [os.path.join(debug_dir, f) for f in os.listdir(debug_dir)]
            if len(files) <= max_files:
                return

            # Sort by modification time (oldest first)
            files.sort(key=os.path.getmtime)
            for f in files[:-max_files]:
                os.remove(f)
        except Exception:
            pass

    async def health_check(self) -> dict[str, Any]:
        """
        Performs a health check on the adapter.
        Subclasses can override to add custom checks.
        """
        return {
            "adapter_name": self.source_name,
            "base_url": self.base_url,
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "metrics": self.metrics.snapshot(),
        }

    def get_status(self) -> dict[str, Any]:
        """
        Returns a dictionary representing the adapter's current status.
        """
        status = "OK"
        if self.circuit_breaker.state == CircuitState.OPEN:
            status = "CIRCUIT_OPEN"
        elif self.metrics.success_rate < 0.5:
            status = "DEGRADED"

        return {
            "adapter_name": self.source_name,
            "status": status,
            "circuit_state": self.circuit_breaker.state.value,
            "success_rate": round(self.metrics.success_rate, 3),
        }

    async def reset(self) -> None:
        """Reset adapter state (cache, circuit breaker, metrics)."""
        if self.cache:
            await self.cache.clear()
        self.circuit_breaker = CircuitBreaker()
        self.metrics = AdapterMetrics()
        self.logger.info("Adapter state reset")
