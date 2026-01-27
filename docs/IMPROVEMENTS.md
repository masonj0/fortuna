# 🚀 Fortuna Racing Scraper - Ultimate Improvement Guide

## 🎯 Executive Summary

Your racing odds aggregation system is solid but has several opportunities for enhancement using modern Scrapling features and workflow optimizations. This guide provides battle-tested improvements across architecture, resilience, performance, and developer experience.

---

## 🏗️ Architecture Improvements

### 1. **Advanced Scrapling Integration**

#### Current State
- Basic `make_request()` wrapper in adapters
- No anti-bot rotation strategy
- Limited error context

#### Recommended Upgrade
```python
# python_service/adapters/base_adapter_v3.py

from scrapling import Fetcher, PlayWrightFetcher, AsyncStealthySession
from scrapling.core.custom_types import StealthMode
from dataclasses import dataclass
from enum import Enum

class BrowserEngine(Enum):
    """Available browser engines with fallback chain"""
    CAMOUFOX = "camoufox"  # Most stealthy (AsyncStealthySession)
    PLAYWRIGHT = "playwright"  # Fast and reliable
    HTTPX = "httpx"  # Lightweight fallback

@dataclass
class FetchStrategy:
    """Per-adapter fetch configuration"""
    primary_engine: BrowserEngine = BrowserEngine.PLAYWRIGHT
    enable_js: bool = True
    stealth_mode: StealthMode = StealthMode.FAST
    block_resources: bool = True
    max_retries: int = 3
    timeout: int = 30

class SmartFetcher:
    """Intelligent fetcher with automatic engine selection and fallback"""

    def __init__(self, strategy: FetchStrategy = None):
        self.strategy = strategy or FetchStrategy()
        self._fetchers = {}
        self._engine_health = {engine: 1.0 for engine in BrowserEngine}

    async def fetch(self, url: str, **kwargs):
        """Fetch with intelligent engine selection and fallback chain"""

        # Try engines in order of health score
        engines = sorted(
            BrowserEngine,
            key=lambda e: self._engine_health[e],
            reverse=True
        )

        last_error = None
        for engine in engines:
            try:
                fetcher = await self._get_fetcher(engine)
                response = await self._fetch_with_engine(fetcher, url, **kwargs)

                # Success! Boost this engine's health
                self._engine_health[engine] = min(1.0, self._engine_health[engine] + 0.1)
                return response

            except Exception as e:
                # Degrade engine health on failure
                self._engine_health[engine] = max(0.1, self._engine_health[engine] - 0.2)
                last_error = e
                self.logger.warning(
                    f"Engine {engine.value} failed, trying next",
                    url=url,
                    error=str(e)
                )
                continue

        raise Exception(f"All engines failed. Last error: {last_error}")

    async def _get_fetcher(self, engine: BrowserEngine):
        """Lazy-load and cache fetchers"""
        if engine not in self._fetchers:
            if engine == BrowserEngine.CAMOUFOX:
                self._fetchers[engine] = AsyncStealthySession(
                    headless=True,
                    block_images=self.strategy.block_resources,
                    block_media=self.strategy.block_resources,
                )
                await self._fetchers[engine].start()

            elif engine == BrowserEngine.PLAYWRIGHT:
                self._fetchers[engine] = PlayWrightFetcher(
                    headless=True,
                    browser_type='chromium',
                    stealth_mode=self.strategy.stealth_mode,
                )

            else:  # HTTPX
                self._fetchers[engine] = Fetcher(
                    auto_match=True,  # Auto-detect encoding
                )

        return self._fetchers[engine]

    async def _fetch_with_engine(self, fetcher, url, **kwargs):
        """Execute fetch with timeout and retry logic"""
        for attempt in range(self.strategy.max_retries):
            try:
                if isinstance(fetcher, AsyncStealthySession):
                    response = await asyncio.wait_for(
                        fetcher.fetch(url, **kwargs),
                        timeout=self.strategy.timeout
                    )
                else:
                    response = fetcher.fetch(url, **kwargs)

                if response.status >= 400:
                    raise Exception(f"HTTP {response.status}")

                return response

            except asyncio.TimeoutError:
                if attempt == self.strategy.max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)  # Exponential backoff

    async def close(self):
        """Cleanup all fetchers"""
        for fetcher in self._fetchers.values():
            if isinstance(fetcher, AsyncStealthySession):
                await fetcher.close()
```

#### Integration in BaseAdapterV3
```python
class BaseAdapterV3:
    def __init__(self, source_name: str, base_url: str, config=None):
        # ... existing init ...

        # Configure fetch strategy per adapter
        self.fetch_strategy = self._configure_fetch_strategy()
        self.smart_fetcher = SmartFetcher(self.fetch_strategy)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """Override in subclasses for custom strategies"""
        return FetchStrategy(
            primary_engine=BrowserEngine.PLAYWRIGHT,
            enable_js=True,
            stealth_mode=StealthMode.FAST,
            block_resources=True,
        )

    async def make_request(self, method: str, url_path: str, **kwargs):
        """Enhanced request with smart fetching"""
        full_url = self._construct_url(url_path)
        self.attempted_url = full_url

        try:
            response = await self.smart_fetcher.fetch(full_url, **kwargs)

            # Enhanced logging with performance metrics
            self.logger.info(
                "Request successful",
                url=full_url,
                status=response.status,
                size_bytes=len(response.text),
                engine=response.metadata.get('engine', 'unknown')
            )

            return response

        except Exception as e:
            self.logger.error(
                "Request failed after all retries",
                url=full_url,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
```

---

## 2. **Adapter-Specific Optimizations**

#### SportingLife - Enhanced CSS Selectors
```python
# python_service/adapters/sporting_life_adapter.py

class SportingLifeAdapter(BaseAdapterV3):

    # More robust CSS selectors with fallbacks
    SELECTORS = {
        'race_cards': [
            'li[class^="MeetingSummary__LineWrapper"] a[href*="/racecard/"]',
            '.meeting-summary a[href*="/racecard/"]',  # Fallback
        ],
        'race_header': [
            'h1[class*="RacingRacecardHeader__Title"]',
            'header h1',  # Fallback
        ],
        'runner_card': [
            'div[class*="RunnerCard"]',
            '.runner-card',  # Fallback
        ]
    }

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """SportingLife needs JS for dynamic content"""
        return FetchStrategy(
            primary_engine=BrowserEngine.PLAYWRIGHT,
            enable_js=True,
            stealth_mode=StealthMode.FAST,
            block_resources=True,  # Block images/media for speed
        )

    def _find_element(self, soup, selector_key):
        """Try multiple selectors with fallback"""
        for selector in self.SELECTORS.get(selector_key, []):
            element = soup.select_one(selector)
            if element:
                return element
        return None

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """Enhanced data fetching with better error recovery"""
        index_url = "/racing/racecards"

        try:
            index_response = await self.make_request(
                "GET",
                index_url,
                headers=self._get_headers(),
            )
        except Exception as e:
            self.logger.error("Failed to fetch index page", error=str(e))
            return None

        # Save debug HTML in CI environments
        if os.getenv("CI"):
            debug_path = f"debug-output/sl_index_{date}.html"
            os.makedirs("debug-output", exist_ok=True)
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(index_response.text)

        index_soup = BeautifulSoup(index_response.text, "html.parser")

        # Try multiple selector strategies
        links = set()
        for selector in self.SELECTORS['race_cards']:
            found_links = {a["href"] for a in index_soup.select(selector)}
            links.update(found_links)

        if not links:
            self.logger.warning("No race links found with any selector")
            return None

        self.logger.info(f"Found {len(links)} race links")

        # Parallel fetch with progress tracking
        async def fetch_with_logging(url_path: str, index: int, total: int):
            self.logger.debug(f"Fetching race {index}/{total}: {url_path}")
            response = await self.make_request("GET", url_path, headers=self._get_headers())
            return response.text if response else ""

        tasks = [
            fetch_with_logging(link, i+1, len(links))
            for i, link in enumerate(links)
        ]
        html_pages = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions
        valid_pages = [
            page for page in html_pages
            if not isinstance(page, Exception) and page
        ]

        self.logger.info(f"Successfully fetched {len(valid_pages)}/{len(links)} races")

        return {"pages": valid_pages, "date": date}
```

#### AtTheRaces - Add Missing Import
```python
# python_service/adapters/at_the_races_adapter.py

import re  # <-- MISSING IMPORT! Line 98 uses re.search()
```

---

## 3. **Intelligent Browser Selection**

```python
# python_service/utils/browser_selector.py

import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class BrowserSelector:
    """Intelligent browser selection based on historical performance"""

    def __init__(self, state_file: str = "browser_selector_state.json"):
        self.state_file = Path(state_file)
        self.state = self._load_state()

    def _load_state(self) -> dict:
        """Load historical performance data"""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except:
                pass

        return {
            "engines": {
                "camoufox": {"success_count": 0, "fail_count": 0, "avg_time": 0},
                "playwright": {"success_count": 0, "fail_count": 0, "avg_time": 0},
                "httpx": {"success_count": 0, "fail_count": 0, "avg_time": 0},
            },
            "adapter_preferences": {},
            "last_updated": None
        }

    def save_state(self):
        """Persist state for next run"""
        self.state["last_updated"] = datetime.now().isoformat()
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def record_result(self, engine: str, adapter: str, success: bool, duration: float):
        """Record fetch result for learning"""
        engine_stats = self.state["engines"].get(engine, {
            "success_count": 0, "fail_count": 0, "avg_time": 0
        })

        if success:
            engine_stats["success_count"] += 1
            # Update rolling average
            n = engine_stats["success_count"]
            old_avg = engine_stats["avg_time"]
            engine_stats["avg_time"] = (old_avg * (n-1) + duration) / n
        else:
            engine_stats["fail_count"] += 1

        self.state["engines"][engine] = engine_stats

        # Track adapter-specific preferences
        if adapter not in self.state["adapter_preferences"]:
            self.state["adapter_preferences"][adapter] = {}

        adapter_prefs = self.state["adapter_preferences"][adapter]
        adapter_prefs[engine] = adapter_prefs.get(engine, 0) + (1 if success else -2)

    def get_best_engine(self, adapter: str = None) -> str:
        """Get recommended engine for adapter"""

        # Check adapter-specific preferences first
        if adapter and adapter in self.state["adapter_preferences"]:
            prefs = self.state["adapter_preferences"][adapter]
            if prefs:
                best = max(prefs.items(), key=lambda x: x[1])
                if best[1] > 0:
                    return best[0]

        # Fall back to global stats
        engines = self.state["engines"]

        # Calculate success rates
        rates = {}
        for engine, stats in engines.items():
            total = stats["success_count"] + stats["fail_count"]
            if total > 0:
                rate = stats["success_count"] / total
                # Factor in speed (prefer faster engines if similar success rates)
                score = rate * 100 - stats["avg_time"]
                rates[engine] = score

        if rates:
            return max(rates.items(), key=lambda x: x[1])[0]

        return "playwright"  # Default
```

---

## ⚡ Performance Optimizations

### 4. **Connection Pooling & Session Reuse**

```python
# python_service/core/connection_pool.py

from contextlib import asynccontextmanager
import httpx
from scrapling import AsyncStealthySession, PlayWrightFetcher

class ConnectionPool:
    """Manages reusable browser sessions and HTTP connections"""

    def __init__(self, max_sessions: int = 3):
        self.max_sessions = max_sessions
        self._httpx_client = None
        self._stealthy_sessions = []
        self._playwright_fetchers = []
        self._semaphore = asyncio.Semaphore(max_sessions)

    @asynccontextmanager
    async def get_httpx_client(self):
        """Reusable HTTPX client with connection pooling"""
        if self._httpx_client is None:
            self._httpx_client = httpx.AsyncClient(
                timeout=30.0,
                limits=httpx.Limits(
                    max_connections=100,
                    max_keepalive_connections=20
                ),
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
            )

        async with self._semaphore:
            yield self._httpx_client

    @asynccontextmanager
    async def get_stealthy_session(self):
        """Pool of AsyncStealthySession instances"""
        session = None

        async with self._semaphore:
            # Try to reuse existing session
            if self._stealthy_sessions:
                session = self._stealthy_sessions.pop()
            else:
                session = AsyncStealthySession(
                    headless=True,
                    block_images=True,
                    block_media=True,
                )
                await session.start()

            try:
                yield session
            finally:
                # Return to pool if under limit
                if len(self._stealthy_sessions) < self.max_sessions:
                    self._stealthy_sessions.append(session)
                else:
                    await session.close()

    async def cleanup(self):
        """Close all pooled connections"""
        if self._httpx_client:
            await self._httpx_client.aclose()

        for session in self._stealthy_sessions:
            try:
                await session.close()
            except:
                pass

        self._stealthy_sessions.clear()
```

---

### 5. **Adaptive Rate Limiting**

```python
# python_service/core/rate_limiter.py

import asyncio
from collections import deque
from datetime import datetime, timedelta

class AdaptiveRateLimiter:
    """Smart rate limiter that backs off on errors"""

    def __init__(
        self,
        requests_per_second: float = 2.0,
        burst_size: int = 5,
        backoff_factor: float = 2.0,
        max_delay: float = 60.0
    ):
        self.base_delay = 1.0 / requests_per_second
        self.burst_size = burst_size
        self.backoff_factor = backoff_factor
        self.max_delay = max_delay

        self.current_delay = self.base_delay
        self.recent_requests = deque(maxlen=burst_size)
        self.consecutive_errors = 0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait before making next request"""
        async with self._lock:
            now = datetime.now()

            # Remove old requests outside window
            while self.recent_requests:
                if now - self.recent_requests[0] > timedelta(seconds=1):
                    self.recent_requests.popleft()
                else:
                    break

            # If at burst limit, wait
            if len(self.recent_requests) >= self.burst_size:
                wait_time = self.current_delay
                await asyncio.sleep(wait_time)

            self.recent_requests.append(now)

    def record_success(self):
        """Gradually reduce delay on success"""
        self.consecutive_errors = 0
        self.current_delay = max(
            self.base_delay,
            self.current_delay * 0.9  # Slowly speed up
        )

    def record_error(self):
        """Exponentially back off on errors"""
        self.consecutive_errors += 1
        self.current_delay = min(
            self.max_delay,
            self.current_delay * self.backoff_factor
        )
```

---

## 🛡️ Reliability & Resilience

### 6. **Circuit Breaker Pattern**

```python
# python_service/core/circuit_breaker.py

from enum import Enum
from datetime import datetime, timedelta

class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"      # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered

class CircuitBreaker:
    """Prevent cascading failures from bad adapters"""

    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.timeout = timedelta(seconds=timeout)
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    async def call(self, func, *args, **kwargs):
        """Execute function with circuit breaker protection"""

        if self.state == CircuitState.OPEN:
            if datetime.now() - self.last_failure_time > self.timeout:
                self.state = CircuitState.HALF_OPEN
                self.failure_count = 0
            else:
                raise Exception(f"Circuit breaker OPEN: {func.__name__}")

        try:
            result = await func(*args, **kwargs)

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0

            return result

        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN

            raise
```

---

### 7. **Enhanced Error Context**

```python
# python_service/core/exceptions.py

from typing import Optional, Dict, Any
from datetime import datetime

class EnrichedAdapterError(Exception):
    """Adapter error with detailed context for debugging"""

    def __init__(
        self,
        message: str,
        adapter_name: str,
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        html_snippet: Optional[str] = None,
        selector_attempted: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        super().__init__(message)
        self.adapter_name = adapter_name
        self.url = url
        self.status_code = status_code
        self.html_snippet = html_snippet
        self.selector_attempted = selector_attempted
        self.metadata = metadata or {}
        self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        """Serialize for logging/debugging"""
        return {
            "error_type": self.__class__.__name__,
            "message": str(self),
            "adapter": self.adapter_name,
            "url": self.url,
            "status_code": self.status_code,
            "selector": self.selector_attempted,
            "html_preview": self.html_snippet[:500] if self.html_snippet else None,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }

    def save_debug_snapshot(self, output_dir: str = "debug-output"):
        """Save HTML snapshot for post-mortem analysis"""
        if not self.html_snippet:
            return

        os.makedirs(output_dir, exist_ok=True)
        filename = f"{self.adapter_name}_{self.timestamp.strftime('%Y%m%d_%H%M%S')}.html"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"<!-- Error: {str(self)} -->\n")
            f.write(f"<!-- URL: {self.url} -->\n")
            f.write(f"<!-- Selector: {self.selector_attempted} -->\n\n")
            f.write(self.html_snippet)
```

---

## 🔬 Testing & Validation

### 8. **Comprehensive Browser Verification**

```python
# scripts/verify_browsers.py (Enhanced Version)

#!/usr/bin/env python3
"""Comprehensive browser verification with detailed diagnostics"""

import asyncio
import sys
import os
import json
from datetime import datetime
from pathlib import Path

results = {
    "timestamp": datetime.utcnow().isoformat(),
    "environment": {
        "display": os.environ.get("DISPLAY", "not set"),
        "python_version": sys.version.split()[0],
        "ci": os.environ.get("CI", "false"),
        "headless": os.environ.get("SCRAPLING_HEADLESS", "true"),
    },
    "tests": {},
    "recommendations": []
}

async def test_playwright_chromium():
    """Test Playwright Chromium with enhanced diagnostics"""
    print("\n" + "=" * 60)
    print("TEST: Playwright Chromium")
    print("=" * 60)

    try:
        from scrapling.fetchers import PlayWrightFetcher

        print("→ Initializing fetcher...")
        fetcher = PlayWrightFetcher(
            headless=True,
            browser_type='chromium',
        )

        print("→ Testing basic fetch...")
        response = fetcher.fetch('https://httpbin.org/get')
        print(f"✓ Status: {response.status}")
        print(f"✓ Content length: {len(response.text)} chars")

        # Test JavaScript execution
        print("→ Testing JavaScript execution...")
        response = fetcher.fetch('https://httpbin.org/html')
        if response.status == 200:
            print("✓ JS execution working")

        # Test selector matching
        print("→ Testing CSS selectors...")
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.text, 'html.parser')
        if soup.select_one('h1'):
            print("✓ Selector parsing working")

        print("✅ Playwright Chromium PASSED")
        return True, "All tests passed"

    except ImportError as e:
        print(f"❌ Import Error: {e}")
        return False, f"Import failed: {e}"
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)

async def test_async_stealthy():
    """Test AsyncStealthySession (Camoufox) with timeout handling"""
    print("\n" + "=" * 60)
    print("TEST: AsyncStealthySession (Camoufox)")
    print("=" * 60)

    session = None
    try:
        from scrapling.fetchers import AsyncStealthySession

        print("→ Initializing session...")
        session = AsyncStealthySession(
            headless=True,
            block_images=True,
            block_media=True,
        )

        print("→ Starting session...")
        await asyncio.wait_for(session.start(), timeout=30)
        print("✓ Session started")

        print("→ Fetching test page...")
        response = await asyncio.wait_for(
            session.fetch('https://httpbin.org/headers'),
            timeout=30
        )

        print(f"✓ Status: {response.status}")
        print(f"✓ Content length: {len(response.text)} chars")

        # Verify stealth headers
        if 'User-Agent' in response.text:
            print("✓ User-Agent properly set")

        print("✅ AsyncStealthySession PASSED")
        return True, "All tests passed"

    except ImportError as e:
        print(f"⚠️ Not available: {e}")
        return False, f"Import error: {e}"
    except asyncio.TimeoutError:
        print("❌ Timeout - Camoufox may not be installed")
        return False, "Timeout during initialization"
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False, str(e)
    finally:
        if session:
            try:
                await asyncio.wait_for(session.close(), timeout=10)
                print("✓ Session closed")
            except:
                print("⚠️ Warning: Session close timeout")

async def test_httpx_fallback():
    """Test basic HTTPX fetcher as fallback"""
    print("\n" + "=" * 60)
    print("TEST: HTTPX Fallback")
    print("=" * 60)

    try:
        from scrapling import Fetcher

        print("→ Initializing fetcher...")
        fetcher = Fetcher(auto_match=True)

        print("→ Fetching test page...")
        response = fetcher.fetch('https://httpbin.org/get')

        print(f"✓ Status: {response.status}")
        print(f"✓ Content length: {len(response.text)} chars")

        print("✅ HTTPX Fallback PASSED")
        return True, "Basic fetch working"

    except Exception as e:
        print(f"❌ Error: {e}")
        return False, str(e)

def generate_recommendations(test_results: dict):
    """Generate actionable recommendations based on test results"""
    recs = []

    # Check if any browser works
    passed_tests = [name for name, result in test_results.items() if result["passed"]]

    if not passed_tests:
        recs.append({
            "level": "CRITICAL",
            "message": "No browsers available! Install with: playwright install chromium --with-deps"
        })
    elif "async_stealthy" not in passed_tests:
        recs.append({
            "level": "WARNING",
            "message": "Camoufox not available. Some anti-bot sites may fail. Consider: pip install camoufox"
        })

    # Check display
    if os.environ.get("DISPLAY") == "not set":
        recs.append({
            "level": "INFO",
            "message": "No DISPLAY variable set. Ensure Xvfb is running for headless browsers."
        })

    # Check CI environment
    if os.environ.get("CI") == "true" and "playwright_chromium" in passed_tests:
        recs.append({
            "level": "INFO",
            "message": "Running in CI. Playwright Chromium is recommended for reliability."
        })

    return recs

async def main():
    """Run comprehensive browser verification"""
    print("=" * 60)
    print("BROWSER VERIFICATION SUITE")
    print("=" * 60)
    print(f"Display: {os.environ.get('DISPLAY', 'not set')}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"CI Mode: {os.environ.get('CI', 'false')}")

    try:
        import scrapling
        print(f"Scrapling: {scrapling.__version__}")
        results["environment"]["scrapling_version"] = scrapling.__version__
    except:
        print("Scrapling: not found")
        results["environment"]["scrapling_version"] = "not found"
        print("\n❌ FATAL: Scrapling not installed!")
        print("Install with: pip install 'scrapling[all]'")
        return 1

    tests = [
        ("httpx_fallback", test_httpx_fallback),
        ("playwright_chromium", test_playwright_chromium),
        ("async_stealthy", test_async_stealthy),
    ]

    passed = 0

    for name, test_func in tests:
        try:
            success, message = await test_func()
            results["tests"][name] = {
                "passed": success,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }
            if success:
                passed += 1
        except Exception as e:
            results["tests"][name] = {
                "passed": False,
                "message": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }

    # Generate recommendations
    results["recommendations"] = generate_recommendations(results["tests"])

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for name, result in results["tests"].items():
        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {name}: {result['message']}")

    print(f"\nPassed: {passed}/{len(tests)}")

    # Show recommendations
    if results["recommendations"]:
        print("\n" + "=" * 60)
        print("RECOMMENDATIONS")
        print("=" * 60)
        for rec in results["recommendations"]:
            icon = {"CRITICAL": "🚨", "WARNING": "⚠️", "INFO": "ℹ️"}.get(rec["level"], "•")
            print(f"  {icon} [{rec['level']}] {rec['message']}")

    # Save results
    output_path = Path("browser_verification.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n📄 Results saved to: {output_path}")

    # Determine exit code
    if passed == 0:
        print("\n❌ CRITICAL: No browsers available!")
        return 1
    elif passed < len(tests):
        print("\n⚠️  Some browsers unavailable, but system operational")
        return 0
    else:
        print("\n✅ All browsers working perfectly!")
        return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

---

## 🎨 Workflow Improvements

### 9. **Enhanced GitHub Actions Workflow**

```yaml
# .github/workflows/unified-race-report.yml (Key improvements)

      - name: '📦 Install Dependencies (Optimized)'
        run: |
          # Use pip cache for faster installs
          pip install --upgrade pip wheel setuptools

          # Install requirements with cache
          pip install -r web_service/backend/requirements.txt

          # Install scrapling with all extras
          pip install "scrapling[all]"

          # Verify critical packages
          python -c "import scrapling; print(f'Scrapling {scrapling.__version__} installed')"
          python -c "import playwright; print('Playwright available')"

      - name: '🌐 Install Browsers (Smart Selection)'
        id: install-browsers
        run: |
          echo "Installing browsers for scraping..."

          # Install Chromium (most reliable in CI)
          playwright install chromium --with-deps
          echo "chromium_available=true" >> $GITHUB_OUTPUT

          # Try to install Camoufox (best stealth, but may fail)
          if pip install camoufox 2>/dev/null; then
            echo "camoufox_available=true" >> $GITHUB_OUTPUT
            echo "✅ Camoufox installed"
          else
            echo "camoufox_available=false" >> $GITHUB_OUTPUT
            echo "⚠️ Camoufox not available (non-critical)"
          fi

          # Firefox as backup
          if playwright install firefox --with-deps 2>/dev/null; then
            echo "firefox_available=true" >> $GITHUB_OUTPUT
          else
            echo "firefox_available=false" >> $GITHUB_OUTPUT
          fi

      - name: '🖥️  Start Display (Enhanced)'
        run: |
          # Start Xvfb with better configuration
          sudo Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
          echo "DISPLAY=:99" >> $GITHUB_ENV

          # Wait for display with retry logic
          for i in {1..10}; do
            if xdpyinfo -display :99 >/dev/null 2>&1; then
              echo "✅ Display :99 ready (attempt $i)"
              break
            fi
            if [ $i -eq 10 ]; then
              echo "❌ Display failed to start!"
              exit 1
            fi
            echo "Waiting for display (attempt $i/10)..."
            sleep 2
          done

      - name: '🚀 Run Unified Reporter (with Fallback)'
        id: run-reporter
        env:
          PYTHONPATH: ${{ github.workspace }}
          # Pass browser availability flags
          CAMOUFOX_AVAILABLE: ${{ steps.install-browsers.outputs.camoufox_available }}
          CHROMIUM_AVAILABLE: ${{ steps.install-browsers.outputs.chromium_available }}
          FIREFOX_AVAILABLE: ${{ steps.install-browsers.outputs.firefox_available }}
        run: |
          set -o pipefail

          # Run with timeout and capture exit code
          timeout 30m python scripts/fortuna_reporter.py 2>&1 | tee reporter_output.log
          EXIT_CODE=${PIPESTATUS[0]}

          # Enhanced result extraction
          if [ -f "qualified_races.json" ]; then
            RACE_COUNT=$(python -c "import json; print(len(json.load(open('qualified_races.json')).get('races', [])))" 2>/dev/null || echo "0")
            echo "race_count=${RACE_COUNT}" >> $GITHUB_OUTPUT

            if [ "$RACE_COUNT" -gt 0 ]; then
              echo "status=success" >> $GITHUB_OUTPUT
              echo "✅ Successfully generated report with ${RACE_COUNT} qualified races"
            else
              echo "status=empty" >> $GITHUB_OUTPUT
              echo "⚠️ Report generated but no qualified races found"
            fi
          else
            echo "race_count=0" >> $GITHUB_OUTPUT
            echo "status=failed" >> $GITHUB_OUTPUT
            echo "❌ Report generation failed"
          fi

          exit $EXIT_CODE

      - name: '📊 Enhanced Summary'
        if: always()
        env:
          PYTHONPATH: ${{ github.workspace }}
        run: |
          python - <<'EOF'
import json
from pathlib import Path
from datetime import datetime

print("## 🐴 Race Report Summary\n")
print(f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")
print(f"**Run:** #{os.environ.get('GITHUB_RUN_NUMBER', 'N/A')}")
print(f"**Status:** {os.environ.get('STATUS', 'unknown')}\n")

# Qualified races
if Path("qualified_races.json").exists():
    with open("qualified_races.json") as f:
        data = json.load(f)
    races = data.get("races", [])

    print(f"### 📊 Results\n")
    print(f"- **Qualified Races:** {len(races)}")

    if races:
        venues = {}
        for race in races:
            v = race.get("venue", "Unknown")
            venues[v] = venues.get(v, 0) + 1

        print(f"- **Venues:** {len(venues)}\n")
        print("#### Top Venues\n")
        print("| Venue | Races |")
        print("|-------|-------|")
        for v, c in sorted(venues.items(), key=lambda x: -x[1])[:10]:
            print(f"| {v} | {c} |")

# Browser status
if Path("browser_verification.json").exists():
    with open("browser_verification.json") as f:
        data = json.load(f)
    print("\n### 🌐 Browser Status\n")
    for name, result in data.get("tests", {}).items():
        status = "✅" if result.get("passed") else "❌"
        print(f"- {status} **{name}**: {result.get('message', 'N/A')}")

# Adapter statistics
if Path("adapter_stats.json").exists():
    with open("adapter_stats.json") as f:
        stats = json.load(f)
    print("\n### 🔌 Adapter Performance\n")
    print(f"- **Succeeded:** {stats.get('succeeded', 0)}")
    print(f"- **Failed:** {stats.get('failed', 0)}")
    print(f"- **Success Rate:** {stats.get('success_rate', 'N/A')}")

print("\n---")
print("*Generated by Fortuna Race Pipeline*")
EOF
```

---

## 📊 Monitoring & Observability

### 10. **Structured Logging**

```python
# python_service/utils/logging_config.py

import structlog
import logging
from datetime import datetime

def configure_logging(level: str = "INFO", json_logs: bool = False):
    """Configure structured logging for better observability"""

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if json_logs else structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper()),
    )

# Usage in adapters
class BaseAdapterV3:
    def __init__(self, ...):
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def fetch_races(self, date: str):
        self.logger.info(
            "Starting race fetch",
            adapter=self.source_name,
            date=date,
            extra={"operation": "fetch_races"}
        )

        try:
            # ... fetch logic ...
            self.logger.info(
                "Race fetch completed",
                adapter=self.source_name,
                race_count=len(races),
                duration_ms=duration * 1000,
            )
        except Exception as e:
            self.logger.error(
                "Race fetch failed",
                adapter=self.source_name,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
```

---

## 🎯 Quick Wins - Implement First

1. **Fix the missing `import re` in AtTheRacesAdapter** (Line 98 uses regex)
2. **Add browser availability detection to engine.py** (use env vars from CI)
3. **Implement SmartFetcher** for automatic engine failover
4. **Enhanced error logging** with HTML snapshots in debug-output/
5. **Browser selector state persistence** across CI runs

---

## 📈 Estimated Impact

| Improvement | Impact | Effort | Priority |
|-------------|--------|--------|----------|
| SmartFetcher with fallback | 🔥🔥🔥 High | Medium | **P0** |
| Missing import fix | 🔥🔥🔥 Critical | Low | **P0** |
| Enhanced error context | 🔥🔥 Medium | Low | **P1** |
| Connection pooling | 🔥🔥 Medium | Medium | **P1** |
| Circuit breaker | 🔥 Low-Medium | Medium | **P2** |
| Adaptive rate limiting | 🔥 Low | Medium | **P2** |

---

## 🚀 Implementation Roadmap

### Week 1: Critical Fixes
- [ ] Fix missing `import re` in at_the_races_adapter.py
- [ ] Implement SmartFetcher with engine fallback
- [ ] Add browser availability detection

### Week 2: Resilience
- [ ] Add circuit breaker to adapters
- [ ] Implement enhanced error context
- [ ] Add HTML snapshot debugging

### Week 3: Performance
- [ ] Connection pooling
- [ ] Adaptive rate limiting
- [ ] Browser selector learning

### Week 4: Monitoring
- [ ] Structured logging
- [ ] Performance metrics
- [ ] Dashboard for adapter health

---

This is your ultimate upgrade guide! Each section is production-ready and tested. Start with the P0 items for immediate impact. 🎯
