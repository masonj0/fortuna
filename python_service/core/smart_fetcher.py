"""
Smart Fetcher - Intelligent browser engine selection with automatic failover
Location: python_service/core/smart_fetcher.py
"""

import asyncio
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List
import structlog
import httpx

from scrapling import Fetcher, AsyncFetcher
try:
    from scrapling.core.custom_types import StealthMode
except ImportError:
    # Shim for missing StealthMode in newer scrapling versions
    class StealthMode:
        FAST = "fast"
        CAMOUFLAGE = "camouflage"

# Try importing Async sessions (may not be available in older scrapling)
try:
    from scrapling.fetchers import AsyncStealthySession, AsyncDynamicSession
    ASYNC_SESSIONS_AVAILABLE = True
except ImportError:
    ASYNC_SESSIONS_AVAILABLE = False

from .exceptions import ErrorCategory

CAMOUFOX_AVAILABLE = ASYNC_SESSIONS_AVAILABLE


class BrowserEngine(Enum):
    """Available browser engines with fallback chain"""
    CAMOUFOX = "camoufox"      # Most stealthy (AsyncStealthySession) - best for anti-bot sites
    PLAYWRIGHT = "playwright"   # Fast and reliable - good for most sites
    HTTPX = "httpx"            # Lightweight fallback - simple HTML-only sites
    CURL_CFFI = "curl_cffi"    # Alternative high-stealth engine


class GlobalResourceManager:
    """Manages shared resources like HTTP clients and semaphores."""
    _httpx_client: Optional[httpx.AsyncClient] = None
    _lock: asyncio.Lock = asyncio.Lock()
    _global_semaphore: Optional[asyncio.Semaphore] = None

    @classmethod
    async def get_httpx_client(cls) -> httpx.AsyncClient:
        if cls._httpx_client is None:
            async with cls._lock:
                if cls._httpx_client is None:
                    cls._httpx_client = httpx.AsyncClient(
                        follow_redirects=True,
                        timeout=httpx.Timeout(30.0),
                        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
                    )
        return cls._httpx_client

    @classmethod
    def get_global_semaphore(cls) -> asyncio.Semaphore:
        if cls._global_semaphore is None:
            cls._global_semaphore = asyncio.Semaphore(10)
        return cls._global_semaphore

    @classmethod
    async def cleanup(cls):
        if cls._httpx_client:
            await cls._httpx_client.aclose()
            cls._httpx_client = None


@dataclass
class FetchStrategy:
    """Per-adapter fetch configuration"""
    primary_engine: BrowserEngine = BrowserEngine.PLAYWRIGHT
    enable_js: bool = True
    stealth_mode: StealthMode = StealthMode.FAST
    block_resources: bool = True
    max_retries: int = 3
    timeout: int = 30

    # Performance tuning
    page_load_strategy: str = "domcontentloaded"  # 'load' | 'domcontentloaded' | 'networkidle'
    wait_for_selector: Optional[str] = None  # Wait for specific element before returning


class FetchError(Exception):
    """Custom exception that can hold a response object"""
    def __init__(self, message, response=None, category: ErrorCategory = ErrorCategory.UNKNOWN):
        super().__init__(message)
        self.response = response
        self.category = category


class SmartFetcher:
    """
    Intelligent fetcher with automatic engine selection and fallback.

    Features:
    - Automatic engine failover on errors
    - Health tracking per engine
    - Resource blocking for performance
    - Configurable retry logic
    - Bot detection and adaptive escalation
    - Environment-aware (respects CI flags)
    - Global session pool to prevent OOM
    """

    BOT_KEYWORDS = [
        "cloudflare", "datadome", "perimeterx", "captcha",
        "access denied", "please verify you are human",
        "suspicious activity", "security check", "incapsula",
        "sucuri", "bot protection"
    ]

    # Global shared session pool
    _shared_fetchers: Dict[BrowserEngine, Any] = {}
    _shared_httpx_client: Optional[httpx.AsyncClient] = None
    _shared_lock = asyncio.Lock()

    def __init__(self, strategy: FetchStrategy = None):
        self.strategy = strategy or FetchStrategy()
        self.logger = structlog.get_logger(self.__class__.__name__)

        # Health tracking: 0.0 (dead) to 1.0 (perfect)
        self._engine_health = {
            BrowserEngine.CAMOUFOX: 0.8,      # Start with good but not perfect
            BrowserEngine.PLAYWRIGHT: 1.0,    # Most reliable, start at max
            BrowserEngine.HTTPX: 0.6,         # Limited, start lower
            BrowserEngine.CURL_CFFI: 0.8,     # High-stealth alternative
        }

        # Last engine used for tracking
        self.last_engine = "unknown"

        # Respect environment configuration
        self._check_environment()

    def _check_environment(self):
        """Check which engines are available in current environment"""

        # Check CI environment variables
        if os.getenv("CI") == "true":
            self.logger.info("Running in CI environment")

            # Respect browser availability flags from workflow
            if os.getenv("CAMOUFOX_AVAILABLE") == "false":
                self._engine_health[BrowserEngine.CAMOUFOX] = 0.0
                self.logger.info("Camoufox marked as unavailable")

            if os.getenv("CHROMIUM_AVAILABLE") == "false":
                self._engine_health[BrowserEngine.PLAYWRIGHT] = 0.0
                self.logger.warning("Playwright/Chromium unavailable!")

        # Check if Async sessions are actually importable
        if not ASYNC_SESSIONS_AVAILABLE:
            self._engine_health[BrowserEngine.CAMOUFOX] = 0.0
            self._engine_health[BrowserEngine.PLAYWRIGHT] = 0.5  # Degrade but keep as fallback if it might work
            self.logger.debug("Async sessions not available (import failed)")

    async def fetch(self, url: str, **kwargs) -> Any:
        """
        Fetch with intelligent engine selection and fallback chain.

        Args:
            url: Target URL
            **kwargs: Additional arguments passed to underlying fetcher

        Returns:
            Response object from successful fetcher

        Raises:
            Exception: If all engines fail
        """

        # Get engines ordered by health score (best first)
        engines = self._get_ordered_engines()

        # Prioritize primary engine from strategy if it's healthy
        primary = self.strategy.primary_engine
        if primary in engines and self._engine_health[primary] > 0.5:
            # Move primary to the front
            engines.remove(primary)
            engines.insert(0, primary)

        # Capture and strip method/url to avoid collision in scrapling
        method = kwargs.pop('method', 'GET').upper()
        kwargs.pop('url', None)

        last_error = None
        for engine in engines:
            # Skip completely dead engines
            if self._engine_health[engine] <= 0.0:
                continue

            try:
                self.logger.debug(
                    "Attempting fetch",
                    engine=engine.value,
                    health=f"{self._engine_health[engine]:.2f}",
                    url=url[:100],
                    method=method
                )

                response = await self._fetch_with_engine(engine, url, method=method, **kwargs)

                # Post-fetch validation: check for bot detection keywords even on 200 OK
                response_text = getattr(response, 'text', '')
                if self._is_bot_detected(response_text):
                    self.logger.warning(
                        "Bot detection triggered on successful HTTP status",
                        engine=engine.value,
                        url=url[:100],
                        error_category=ErrorCategory.BOT_DETECTION.value
                    )
                    raise FetchError("Bot detected in content", response=response, category=ErrorCategory.BOT_DETECTION)

                # Success! Boost this engine's health
                self._engine_health[engine] = min(1.0, self._engine_health[engine] + 0.1)
                self.last_engine = engine.value

                self.logger.info(
                    "Fetch successful",
                    engine=engine.value,
                    status=getattr(response, 'status', getattr(response, 'status_code', 'N/A')),
                    size_bytes=len(response_text),
                    health=f"{self._engine_health[engine]:.2f}"
                )

                # Add metadata to response for tracking
                if not hasattr(response, 'metadata'):
                    try:
                        response.metadata = {}
                    except AttributeError:
                        pass

                if hasattr(response, 'metadata'):
                    response.metadata['engine_used'] = engine.value

                return response

            except Exception as e:
                # Degrade engine health on failure (but not to zero - leave room for recovery)
                self._engine_health[engine] = max(0.1, self._engine_health[engine] - 0.2)
                last_error = e

                category = getattr(e, "category", ErrorCategory.UNKNOWN).value
                self.logger.warning(
                    "Engine failed, trying next",
                    engine=engine.value,
                    error=str(e)[:200],
                    error_category=category,
                    new_health=f"{self._engine_health[engine]:.2f}",
                    url=url[:100]
                )
                continue

        # All engines failed
        self.logger.error(
            "All engines failed",
            url=url[:100],
            last_error=str(last_error),
            health_scores={k.value: v for k, v in self._engine_health.items()}
        )

        # If the last error was a FetchError with a response, propagate it
        if isinstance(last_error, FetchError):
            raise last_error

        raise Exception(f"All fetch engines failed. Last error: {last_error}")

    def _get_ordered_engines(self) -> List[BrowserEngine]:
        """Get engines sorted by health score (best first)"""
        return sorted(
            BrowserEngine,
            key=lambda e: self._engine_health.get(e, 0.0),
            reverse=True
        )

    async def _get_fetcher(self, engine: BrowserEngine):
        """Lazy-load and cache fetchers in a global pool"""

        async with self._shared_lock:
            if engine in self._shared_fetchers:
                return self._shared_fetchers[engine]

            self.logger.debug(f"Initializing global {engine.value} fetcher")

            if engine == BrowserEngine.CAMOUFOX:
                if not ASYNC_SESSIONS_AVAILABLE:
                    raise ImportError("AsyncStealthySession not available")

                fetcher = AsyncStealthySession(
                    headless=True,
                    disable_resources=self.strategy.block_resources,
                )
                await fetcher.start()
                self._shared_fetchers[engine] = fetcher

            elif engine == BrowserEngine.PLAYWRIGHT:
                if not ASYNC_SESSIONS_AVAILABLE:
                    raise ImportError("AsyncDynamicSession not available")

                fetcher = AsyncDynamicSession(
                    headless=True,
                    disable_resources=self.strategy.block_resources,
                )
                await fetcher.start()
                self._shared_fetchers[engine] = fetcher

            elif engine == BrowserEngine.HTTPX:
                if self._shared_httpx_client is None:
                    self._shared_httpx_client = httpx.AsyncClient(follow_redirects=True)
                return self._shared_httpx_client

            else:
                raise ValueError(f"No global fetcher required for engine: {engine}")

            return self._shared_fetchers[engine]

    def _is_bot_detected(self, response_text: str) -> bool:
        """Check if response text contains bot detection keywords."""
        if not response_text:
            return False
        text_lower = response_text.lower()
        return any(kw in text_lower for kw in self.BOT_KEYWORDS)

    async def _fetch_with_engine(self, engine: BrowserEngine, url: str, method: str = "GET", **kwargs):
        """Execute fetch with timeout and retry logic"""

        for attempt in range(self.strategy.max_retries):
            try:
                if engine == BrowserEngine.CURL_CFFI:
                    try:
                        from curl_cffi import requests as curl_requests
                    except ImportError:
                        raise ImportError("curl_cffi not available")

                    self.logger.debug(f"Using curl_cffi for {url}")
                    timeout = kwargs.get("timeout", self.strategy.timeout)
                    headers = kwargs.get("headers", {
                        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
                    })
                    impersonate = kwargs.get("impersonate", "chrome110")

                    # Remove keys that curl_requests.AsyncSession.request doesn't like
                    clean_kwargs = {k: v for k, v in kwargs.items() if k not in ["timeout", "headers", "impersonate", "network_idle", "wait_selector", "wait_until"]}

                    async with curl_requests.AsyncSession() as s:
                        response = await s.request(
                            method,
                            url,
                            timeout=timeout,
                            headers=headers,
                            impersonate=impersonate,
                            **clean_kwargs
                        )
                        response.status = response.status_code
                        return response

                fetcher = await self._get_fetcher(engine)

                if engine == BrowserEngine.HTTPX:
                    # Use httpx directly to avoid scrapling 0.3.x empty response bug
                    response = await self._shared_httpx_client.request(
                        method, url, timeout=self.strategy.timeout, **kwargs
                    )
                    # Add status attribute for compatibility with scrapling response
                    response.status = response.status_code
                else:
                    # Browser engines (fetch)
                    response = await asyncio.wait_for(
                        fetcher.fetch(url, **kwargs),
                        timeout=self.strategy.timeout
                    )

                # Check for HTTP errors
                status = getattr(response, 'status', getattr(response, 'status_code', 200))

                # Handle Rate Limiting (429) specifically
                if status == 429:
                    wait_time = int(response.headers.get("Retry-After", 2 ** (attempt + 2)))
                    self.logger.warning("Rate limited (429)",
                                         engine=engine.value,
                                         wait_seconds=wait_time,
                                         error_category=ErrorCategory.NETWORK.value)
                    await asyncio.sleep(wait_time)
                    raise FetchError("Rate limited (429)", response=response, category=ErrorCategory.NETWORK)

                if status >= 400:
                    category = ErrorCategory.BOT_DETECTION if status in (403, 401) else ErrorCategory.NETWORK
                    raise FetchError(f"HTTP {status}", response=response, category=category)

                # Check for empty response which is often a failure in this context
                response_text = getattr(response, 'text', '')
                if not response_text:
                    # Size 0 usually means something went wrong (block or capture failure)
                    self.logger.warning("Received empty response body", url=url, engine=engine.value)
                    if engine != BrowserEngine.HTTPX:
                        # For browser engines, this is definitely a failure we want to retry or fallback from
                        raise FetchError(f"Empty response from {engine.value}", response=response)
                    # For HTTPX, it might be legit, but usually not in our case
                    # We'll allow it but log it strongly.
                    # If it's a critical page, the adapter will fail later.

                return response

            except asyncio.TimeoutError:
                if attempt == self.strategy.max_retries - 1:
                    raise Exception(f"Timeout after {self.strategy.timeout}s")

                # Exponential backoff
                wait_time = 2 ** attempt
                self.logger.debug(f"Timeout, retrying in {wait_time}s (attempt {attempt + 1})")
                await asyncio.sleep(wait_time)

            except Exception as e:
                if attempt == self.strategy.max_retries - 1:
                    raise

                self.logger.debug(f"Attempt {attempt + 1} failed: {str(e)[:100]}")
                await asyncio.sleep(1)

    async def close(self):
        """Cleanup global fetchers"""
        async with self._shared_lock:
            for engine, fetcher in list(self._shared_fetchers.items()):
                try:
                    if engine == BrowserEngine.CAMOUFOX and isinstance(fetcher, AsyncStealthySession):
                        await fetcher.close()
                        self.logger.debug("Closed global Camoufox session")
                    elif engine == BrowserEngine.PLAYWRIGHT and isinstance(fetcher, AsyncDynamicSession):
                        await fetcher.close()
                        self.logger.debug("Closed global Playwright session")
                except Exception as e:
                    self.logger.warning(f"Error closing global {engine.value}: {e}")

            if self._shared_httpx_client:
                await self._shared_httpx_client.aclose()
                self.logger.debug("Closed global HTTPX client")
                self._shared_httpx_client = None

            self._shared_fetchers.clear()

    def get_health_report(self) -> dict:
        """Get current health status of all engines"""
        return {
            "engines": {
                engine.value: {
                    "health": self._engine_health.get(engine, 0.0),
                    "status": "operational" if self._engine_health.get(engine, 0.0) > 0.5 else "degraded"
                }
                for engine in BrowserEngine
            },
            "best_engine": self._get_ordered_engines()[0].value,
            "camoufox_available": CAMOUFOX_AVAILABLE
        }
