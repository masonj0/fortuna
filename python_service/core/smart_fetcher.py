"""
Smart Fetcher - Intelligent browser engine selection with automatic failover
Location: python_service/core/smart_fetcher.py
"""

import asyncio
import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
import structlog

from scrapling import Fetcher, StealthyFetcher as PlayWrightFetcher
try:
    from scrapling.core.custom_types import StealthMode
except ImportError:
    # Shim for missing StealthMode in newer scrapling versions
    class StealthMode:
        FAST = "fast"
        CAMOUFLAGE = "camouflage"

# Try importing AsyncStealthySession (may not be available)
try:
    from scrapling.fetchers import AsyncStealthySession
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False


class BrowserEngine(Enum):
    """Available browser engines with fallback chain"""
    CAMOUFOX = "camoufox"      # Most stealthy (AsyncStealthySession) - best for anti-bot sites
    PLAYWRIGHT = "playwright"   # Fast and reliable - good for most sites
    HTTPX = "httpx"            # Lightweight fallback - simple HTML-only sites


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


class SmartFetcher:
    """
    Intelligent fetcher with automatic engine selection and fallback.

    Features:
    - Automatic engine failover on errors
    - Health tracking per engine
    - Resource blocking for performance
    - Configurable retry logic
    - Environment-aware (respects CI flags)
    """

    def __init__(self, strategy: FetchStrategy = None):
        self.strategy = strategy or FetchStrategy()
        self.logger = structlog.get_logger(self.__class__.__name__)

        # Track fetcher instances (lazy-loaded)
        self._fetchers: Dict[BrowserEngine, Any] = {}

        # Health tracking: 0.0 (dead) to 1.0 (perfect)
        self._engine_health = {
            BrowserEngine.CAMOUFOX: 0.8,      # Start with good but not perfect
            BrowserEngine.PLAYWRIGHT: 1.0,    # Most reliable, start at max
            BrowserEngine.HTTPX: 0.6,         # Limited, start lower
        }

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

        # Check if Camoufox is actually importable
        if not CAMOUFOX_AVAILABLE:
            self._engine_health[BrowserEngine.CAMOUFOX] = 0.0
            self.logger.debug("AsyncStealthySession not available (import failed)")

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
                    url=url[:100]
                )

                fetcher = await self._get_fetcher(engine)
                response = await self._fetch_with_engine(fetcher, engine, url, **kwargs)

                # Success! Boost this engine's health
                self._engine_health[engine] = min(1.0, self._engine_health[engine] + 0.1)

                self.logger.info(
                    "Fetch successful",
                    engine=engine.value,
                    status=getattr(response, 'status', 'N/A'),
                    size_bytes=len(getattr(response, 'text', '')),
                    health=f"{self._engine_health[engine]:.2f}"
                )

                # Add metadata to response for tracking
                if hasattr(response, 'metadata'):
                    response.metadata['engine_used'] = engine.value

                return response

            except Exception as e:
                # Degrade engine health on failure (but not to zero - leave room for recovery)
                self._engine_health[engine] = max(0.1, self._engine_health[engine] - 0.2)
                last_error = e

                self.logger.warning(
                    "Engine failed, trying next",
                    engine=engine.value,
                    error=str(e)[:200],
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
        raise Exception(f"All fetch engines failed. Last error: {last_error}")

    def _get_ordered_engines(self) -> list[BrowserEngine]:
        """Get engines sorted by health score (best first)"""
        return sorted(
            BrowserEngine,
            key=lambda e: self._engine_health[e],
            reverse=True
        )

    async def _get_fetcher(self, engine: BrowserEngine):
        """Lazy-load and cache fetchers"""

        if engine in self._fetchers:
            return self._fetchers[engine]

        self.logger.debug(f"Initializing {engine.value} fetcher")

        if engine == BrowserEngine.CAMOUFOX:
            if not CAMOUFOX_AVAILABLE:
                raise ImportError("AsyncStealthySession not available")

            fetcher = AsyncStealthySession(
                headless=True,
                block_images=self.strategy.block_resources,
                block_media=self.strategy.block_resources,
            )
            await fetcher.start()
            self._fetchers[engine] = fetcher

        elif engine == BrowserEngine.PLAYWRIGHT:
            # In scrapling 0.3.x, StealthyFetcher is the replacement for PlayWrightFetcher
            fetcher = PlayWrightFetcher()
            self._fetchers[engine] = fetcher

        else:  # HTTPX
            fetcher = Fetcher()
            self._fetchers[engine] = fetcher

        return self._fetchers[engine]

    async def _fetch_with_engine(self, fetcher, engine: BrowserEngine, url: str, **kwargs):
        """Execute fetch with timeout and retry logic"""

        for attempt in range(self.strategy.max_retries):
            try:
                # Handle AsyncStealthySession specially (needs await)
                if engine == BrowserEngine.CAMOUFOX:
                    response = await asyncio.wait_for(
                        fetcher.fetch(url, **kwargs),
                        timeout=self.strategy.timeout
                    )
                else:
                    # Playwright (StealthyFetcher) has fetch(), but HTTPX (Fetcher) uses get()
                    if engine == BrowserEngine.PLAYWRIGHT:
                        response = fetcher.fetch(url, **kwargs)
                    else:
                        response = fetcher.get(url, **kwargs)

                # Check for HTTP errors
                if hasattr(response, 'status') and response.status >= 400:
                    raise Exception(f"HTTP {response.status}")

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
        """Cleanup all fetchers"""
        for engine, fetcher in self._fetchers.items():
            try:
                if engine == BrowserEngine.CAMOUFOX and isinstance(fetcher, AsyncStealthySession):
                    await fetcher.close()
                    self.logger.debug("Closed Camoufox session")
            except Exception as e:
                self.logger.warning(f"Error closing {engine.value}: {e}")

        self._fetchers.clear()

    def get_health_report(self) -> dict:
        """Get current health status of all engines"""
        return {
            "engines": {
                engine.value: {
                    "health": self._engine_health[engine],
                    "status": "operational" if self._engine_health[engine] > 0.5 else "degraded"
                }
                for engine in BrowserEngine
            },
            "best_engine": self._get_ordered_engines()[0].value,
            "camoufox_available": CAMOUFOX_AVAILABLE
        }


# Example usage in adapters
if __name__ == "__main__":
    async def test_smart_fetcher():
        """Test the SmartFetcher"""

        fetcher = SmartFetcher(
            FetchStrategy(
                primary_engine=BrowserEngine.PLAYWRIGHT,
                block_resources=True,
                timeout=30
            )
        )

        try:
            # Test fetch
            response = await fetcher.fetch("https://httpbin.org/html")
            print(f"✅ Fetch successful: {response.status}")
            print(f"Content length: {len(response.text)} bytes")

            # Show health report
            health = fetcher.get_health_report()
            print(f"\n📊 Health Report:")
            for engine, status in health["engines"].items():
                print(f"  {engine}: {status['health']:.2f} ({status['status']})")
            print(f"  Best engine: {health['best_engine']}")

        finally:
            await fetcher.close()

    asyncio.run(test_smart_fetcher())
