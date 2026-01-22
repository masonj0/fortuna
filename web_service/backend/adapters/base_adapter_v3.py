# python_service/adapters/base_v3.py
from __future__ import annotations

import asyncio
import hashlib
import json
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

from ..core.exceptions import AdapterHttpError, AdapterParsingError
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

    async def __aenter__(self) -> "BaseAdapterV3":
        """Async context manager entry."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with cleanup."""
        await self.close()

    async def close(self) -> None:
        """Clean up resources."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
        if self.cache:
            await self.cache.clear()
        self.logger.debug("Adapter resources cleaned up")
        # Resilience components
        self.circuit_breaker = CircuitBreaker()
        self.rate_limiter = RateLimiter(requests_per_second=rate_limit)
        self.cache = ResponseCache(default_ttl=cache_ttl) if enable_cache else None
        self.metrics = AdapterMetrics()

    async def __aenter__(self) -> "BaseAdapterV3":
        """Async context manager entry."""
        if self.http_client is None:
            self.http_client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit with cleanup."""
        await self.close()

    async def close(self) -> None:
        """Clean up resources."""
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
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
        is_valid, reason = DataValidationPipeline.validate_raw_response(self.source_name, raw_data)
        if not is_valid:
            raise AdapterParsingError(self.source_name, f"Raw response validation failed: {reason}")

        try:
            parsed_races = self._parse_races(raw_data)
        except Exception as e:
            self.logger.error("Failed to parse race data", error=str(e))
            raise AdapterParsingError(self.source_name, "Parsing logic failed.") from e

        validated_races, warnings = DataValidationPipeline.validate_parsed_races(parsed_races)

        if warnings:
            self.logger.warning("Validation warnings during parsing", warnings=warnings)

        return validated_races

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
        if not await self.circuit_breaker.allow_request():
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
            await self.metrics.record_success(latency_ms)
            await self.circuit_breaker.record_success()

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
            await self.metrics.record_failure(f"HTTP {e.response.status_code}")
            await self.circuit_breaker.record_failure()

            raise AdapterHttpError(
                adapter_name=self.source_name,
                status_code=e.response.status_code,
                url=str(e.request.url),
                message=f"HTTP {e.response.status_code}: {e.response.reason_phrase}",
                response_body=e.response.text[:500] if e.response.text else None,
                request_method=method.upper(),
            ) from e

        except (httpx.RequestError, RetryError) as e:
            self.logger.error("Request error", error=str(e))
            await self.metrics.record_failure(str(e))
            await self.circuit_breaker.record_failure()

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
