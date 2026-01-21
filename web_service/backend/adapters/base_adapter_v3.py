# python_service/adapters/base_v3.py
from __future__ import annotations

import asyncio
import hashlib
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

from ..core.exceptions import AdapterHttpError
from ..manual_override_manager import ManualOverrideManager
from ..models import Race

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Simple circuit breaker implementation."""
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 3

    _failure_count: int = field(default=0, repr=False)
    _last_failure_time: float = field(default=0.0, repr=False)
    _state: CircuitState = field(default=CircuitState.CLOSED, repr=False)
    _half_open_calls: int = field(default=0, repr=False)

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
        return self._state

    def record_success(self) -> None:
        """Record a successful call."""
        self._failure_count = 0
        if self._state == CircuitState.HALF_OPEN:
            self._half_open_calls += 1
            if self._half_open_calls >= self.half_open_max_calls:
                self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call."""
        self._failure_count += 1
        self._last_failure_time = time.monotonic()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
        elif self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.OPEN

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        state = self.state
        if state == CircuitState.CLOSED:
            return True
        if state == CircuitState.HALF_OPEN:
            return True
        return False


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
        """Generate a cache key from request parameters."""
        key_data = f"{method}:{url}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

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
    """Metrics for adapter health monitoring."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    last_success: float | None = None
    last_failure: float | None = None
    last_error: str | None = None

    @property
    def success_rate(self) -> float:
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_requests == 0:
            return 0.0
        return self.total_latency_ms / self.successful_requests

    def record_success(self, latency_ms: float) -> None:
        self.total_requests += 1
        self.successful_requests += 1
        self.total_latency_ms += latency_ms
        self.last_success = time.time()

    def record_failure(self, error: str) -> None:
        self.total_requests += 1
        self.failed_requests += 1
        self.last_failure = time.time()
        self.last_error = error


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

    # Default User-Agent for requests
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

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

        # Resilience components
        self.circuit_breaker = CircuitBreaker()
        self.rate_limiter = RateLimiter(requests_per_second=rate_limit)
        self.cache = ResponseCache(default_ttl=cache_ttl) if enable_cache else None
        self.metrics = AdapterMetrics()

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
            try:
                return self._parse_races(raw_data)
            except Exception as e:
                self.logger.error("Failed to parse race data", error=str(e))
                raise

        return []

    @retry(
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def make_request(
        self,
        http_client: httpx.AsyncClient,
        method: str,
        url: str,
        use_cache: bool = True,
        cache_ttl: float | None = None,
        **kwargs,
    ) -> httpx.Response:
        """
        Makes a resilient HTTP request with:
        - Circuit breaker protection
        - Rate limiting
        - Response caching
        - Retry logic with exponential backoff
        """
        # Build full URL
        full_url = url if url.startswith("http") else f"{self.base_url}/{url.lstrip('/')}"

        # Check circuit breaker
        if not self.circuit_breaker.allow_request():
            self.logger.warning("Circuit breaker open, rejecting request", url=full_url)
            raise AdapterHttpError(
                adapter_name=self.source_name,
                status_code=503,
                url=full_url,
                message="Circuit breaker is open"
            )

        # Check cache for GET requests
        if use_cache and self.cache and method.upper() == "GET":
            cached = await self.cache.get(method, full_url, **kwargs)
            if cached is not None:
                self.logger.debug("Cache hit", url=full_url)
                return cached

        # Apply rate limiting
        await self.rate_limiter.acquire()

        # Pop headers and follow_redirects from kwargs to pass them explicitly.
        headers = kwargs.pop("headers", {})
        if "User-Agent" not in headers:
            headers["User-Agent"] = self.DEFAULT_USER_AGENT

        follow_redirects = kwargs.pop("follow_redirects", True)

        start_time = time.monotonic()

        try:
            self.logger.info("Making request", method=method.upper(), url=full_url)

            response = await http_client.request(
                method,
                full_url,
                timeout=self.timeout,
                headers=headers,
                follow_redirects=follow_redirects,
                **kwargs,  # Pass remaining kwargs
            )
            response.raise_for_status()

            # Record success
            latency_ms = (time.monotonic() - start_time) * 1000
            self.metrics.record_success(latency_ms)
            self.circuit_breaker.record_success()

            # Cache successful GET responses
            if use_cache and self.cache and method.upper() == "GET":
                await self.cache.set(method, full_url, response, ttl=cache_ttl, **kwargs)

            return response

        except httpx.HTTPStatusError as e:
            self.logger.error(
                "HTTP status error",
                status_code=e.response.status_code,
                url=str(e.request.url),
            )
            self.metrics.record_failure(f"HTTP {e.response.status_code}")
            self.circuit_breaker.record_failure()

            raise AdapterHttpError(
                adapter_name=self.source_name,
                status_code=e.response.status_code,
                url=str(e.request.url),
            ) from e

        except (httpx.RequestError, RetryError) as e:
            self.logger.error("Request error", error=str(e))
            self.metrics.record_failure(str(e))
            self.circuit_breaker.record_failure()

            raise AdapterHttpError(
                adapter_name=self.source_name,
                status_code=503,
                url=full_url,
            ) from e

    async def health_check(self) -> dict[str, Any]:
        """
        Performs a health check on the adapter.
        Subclasses can override to add custom checks.
        """
        return {
            "adapter_name": self.source_name,
            "base_url": self.base_url,
            "circuit_breaker_state": self.circuit_breaker.state.value,
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "success_rate": round(self.metrics.success_rate, 3),
                "avg_latency_ms": round(self.metrics.avg_latency_ms, 1),
                "last_success": self.metrics.last_success,
                "last_failure": self.metrics.last_failure,
                "last_error": self.metrics.last_error,
            },
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
