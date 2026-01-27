# 🎯 Adapter Pattern Quick Reference

**Use this as a cheat sheet when updating adapters to use SmartFetcher**

---

## 📋 Adapter Update Checklist

### Required Changes (All Adapters)
- [ ] Add `from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy`
- [ ] Implement `_configure_fetch_strategy()` method
- [ ] Verify `make_request()` inherited from BaseAdapterV3
- [ ] Test with your chosen engine

### Optional Enhancements
- [ ] Add mixins (BrowserHeadersMixin, DebugMixin)
- [ ] Switch to Selectolax for faster parsing
- [ ] Add fallback CSS selectors
- [ ] Implement debug HTML saving

---

## 🎨 Pattern Templates

### Pattern 1: Simple HTML Site (No JavaScript)
**Use Case**: Static content, simple HTML structure
**Examples**: AtTheRaces, simple results pages, API endpoints

```python
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy

class SimpleAdapter(BaseAdapterV3):
    """Adapter for simple HTML sites"""

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """Use HTTPX - fastest for static HTML"""
        return FetchStrategy(
            primary_engine=BrowserEngine.HTTPX,
            enable_js=False,
            timeout=20,
            max_retries=2
        )

    async def _fetch_data(self, date: str):
        # HTTPX will be used automatically via make_request()
        response = await self.make_request("GET", f"/racecards/{date}")
        return {"html": response.text, "date": date}
```

**When to Use**:
- ✅ Content visible in "View Source"
- ✅ No "Loading..." spinners
- ✅ Fast page load times
- ✅ Works with curl/wget

---

### Pattern 2: JavaScript-Rendered Content
**Use Case**: Dynamic content, SPA, React/Vue apps
**Examples**: SportingLife, modern racing sites

```python
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy

class JavaScriptAdapter(BaseAdapterV3):
    """Adapter for JS-heavy sites"""

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """Use Playwright - handles JS execution"""
        return FetchStrategy(
            primary_engine=BrowserEngine.PLAYWRIGHT,
            enable_js=True,
            block_resources=True,  # Block images/fonts for speed
            timeout=30,
            page_load_strategy="domcontentloaded"  # Don't wait for all resources
        )

    async def _fetch_data(self, date: str):
        # Playwright will execute JS and wait for DOM
        response = await self.make_request("GET", f"/racing/{date}")
        return {"html": response.text, "date": date}
```

**When to Use**:
- ✅ Content NOT in "View Source"
- ✅ "Loading..." spinners present
- ✅ API calls visible in Network tab
- ✅ React/Vue/Angular framework

---

### Pattern 3: Anti-Bot Protection
**Use Case**: Sites with Cloudflare, PerimeterX, bot detection
**Examples**: RacingPost, premium bookmakers, protected APIs

```python
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy
from scrapling.core.custom_types import StealthMode

class StealthAdapter(BaseAdapterV3):
    """Adapter for bot-protected sites"""

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """Use Camoufox - maximum stealth"""
        return FetchStrategy(
            primary_engine=BrowserEngine.CAMOUFOX,
            enable_js=True,
            stealth_mode=StealthMode.CAMOUFLAGE,  # Maximum stealth
            block_resources=True,
            timeout=45,  # Allow extra time for stealth operations
            max_retries=4
        )

    async def _fetch_data(self, date: str):
        # Camoufox will use anti-detection techniques
        response = await self.make_request("GET", f"/odds/{date}")
        return {"html": response.text, "date": date}
```

**When to Use**:
- ✅ Cloudflare "Checking your browser" page
- ✅ Captchas appear
- ✅ 403 Forbidden errors with normal requests
- ✅ "Bot detected" messages

---

### Pattern 4: API Endpoints
**Use Case**: JSON APIs, authenticated endpoints
**Examples**: Betfair API, official racing APIs

```python
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy

class ApiAdapter(BaseAdapterV3):
    """Adapter for API endpoints"""

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """Use HTTPX - APIs don't need browsers"""
        return FetchStrategy(
            primary_engine=BrowserEngine.HTTPX,
            enable_js=False,
            timeout=15,
            max_retries=3
        )

    def _get_headers(self) -> dict:
        """Add API authentication"""
        return {
            "Authorization": f"Bearer {self.config.API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    async def _fetch_data(self, date: str):
        response = await self.make_request(
            "GET",
            f"/api/v1/races?date={date}",
            headers=self._get_headers()
        )
        return response.json()  # Direct JSON parsing
```

**When to Use**:
- ✅ Official API with documentation
- ✅ JSON responses
- ✅ Authentication required
- ✅ Rate limits mentioned

---

## 🔧 Parser Recommendations

### BeautifulSoup → Selectolax Migration
**Benefit**: 5x faster parsing

```python
# OLD (BeautifulSoup)
from bs4 import BeautifulSoup
soup = BeautifulSoup(html, "html.parser")
node = soup.select_one("h1")
name = node.get_text()

# NEW (Selectolax)
from selectolax.parser import HTMLParser
parser = HTMLParser(html)
node = parser.css_first("h1")
name = node.text()
```

**Key Differences**:
- `select_one()` → `css_first()`
- `select()` → `css()`
- `get_text()` → `text()`
- `find()` → `css_first()` with CSS selector

---

## 🎯 Decision Matrix

### Which Engine Should I Use?

| Site Characteristics | Recommended Engine | Backup Engine |
|---------------------|-------------------|---------------|
| Static HTML, fast loading | HTTPX | Playwright |
| JavaScript rendering | Playwright | Camoufox |
| Anti-bot protection | Camoufox | Playwright |
| Official JSON API | HTTPX | N/A |
| Cloudflare protected | Camoufox | N/A |
| Mobile-only content | Playwright (mobile UA) | Camoufox |

### Speed vs Stealth Trade-off

```
HTTPX          ⚡⚡⚡⚡⚡  🥷
Playwright     ⚡⚡⚡⚡    🥷🥷
Camoufox       ⚡⚡       🥷🥷🥷🥷🥷

⚡ = Speed
🥷 = Stealth
```

---

## 🧪 Testing Your Adapter

### Quick Test Script
```python
#!/usr/bin/env python3
"""Quick adapter test"""

import asyncio
from python_service.adapters.your_adapter import YourAdapter

async def test():
    adapter = YourAdapter()

    try:
        print("Fetching races...")
        races = await adapter.fetch_races("2026-01-27")

        print(f"✅ Found {len(races)} races")

        # Check health
        if hasattr(adapter, 'smart_fetcher'):
            health = adapter.smart_fetcher.get_health_report()
            print(f"Engine used: {health['best_engine']}")

    finally:
        # Cleanup
        if hasattr(adapter, 'smart_fetcher'):
            await adapter.smart_fetcher.close()

asyncio.run(test())
```

### Manual Testing Steps
1. **View Source Test**: Can you see content in "View Page Source"?
   - Yes → Try HTTPX first
   - No → Use Playwright or Camoufox

2. **Network Tab Test**: Check browser DevTools Network tab
   - XHR/Fetch requests → Consider API approach
   - Many resources → Enable `block_resources=True`

3. **Bot Detection Test**: Try with curl
   ```bash
   curl -L "https://site.com/racecards/2026-01-27"
   ```
   - Works → HTTPX sufficient
   - 403/captcha → Use Camoufox

---

## 📚 Common Patterns

### Pattern: Fallback CSS Selectors
```python
SELECTORS = {
    "horse_name": [
        "h3.horse-name",           # Current selector
        ".runner-name",            # Fallback 1
        '[data-test="horse-name"]' # Fallback 2
    ]
}

def _find_first_match(self, parser, selector_list):
    """Try selectors until one works"""
    for selector in selector_list:
        if node := parser.css_first(selector):
            return node
    return None
```

### Pattern: Debug HTML Saving
```python
def _should_save_debug(self) -> bool:
    """Save in CI or debug mode"""
    return os.getenv("CI") == "true" or os.getenv("DEBUG_MODE") == "true"

def _save_debug_html(self, html: str, filename: str):
    """Save HTML snapshot for debugging"""
    if not self._should_save_debug():
        return

    os.makedirs("debug-output", exist_ok=True)
    path = f"debug-output/{self.source_name}_{filename}.html"

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"<!-- Generated: {datetime.now()} -->\n")
        f.write(f"<!-- Adapter: {self.source_name} -->\n\n")
        f.write(html)
```

### Pattern: Robust Error Handling
```python
async def _fetch_data(self, date: str) -> Optional[dict]:
    """Fetch with proper error handling"""
    try:
        response = await self.make_request("GET", f"/races/{date}")
    except Exception as e:
        self.logger.error(
            "Fetch failed",
            date=date,
            error=str(e),
            error_type=type(e).__name__
        )
        return None

    if not response or not response.text:
        self.logger.warning("Empty response", date=date)
        return None

    # Save debug snapshot on error
    self._save_debug_html(response.text, f"success_{date}")

    return {"html": response.text, "date": date}
```

---

## 🎓 Pro Tips

### Tip 1: Start Simple
Begin with HTTPX, upgrade to Playwright only if needed:
```python
# Day 1: Start here
primary_engine=BrowserEngine.HTTPX

# Day 2: If HTTPX fails, upgrade
primary_engine=BrowserEngine.PLAYWRIGHT
```

### Tip 2: Use Environment Variables
```python
# Allow override via env vars
engine_choice = os.getenv("ADAPTER_ENGINE", "playwright").upper()
primary_engine = BrowserEngine[engine_choice]
```

### Tip 3: Log Health After Fetch
```python
async def fetch_races(self, date: str):
    races = await self._fetch_and_parse(date)

    # Log engine performance
    if hasattr(self, 'smart_fetcher'):
        health = self.smart_fetcher.get_health_report()
        self.logger.info(
            "Fetch complete",
            races_found=len(races),
            engine_used=health['best_engine'],
            engine_health=health['engines']
        )

    return races
```

### Tip 4: Test Failover
```python
# Force failover to test it works
async def test_failover():
    adapter = YourAdapter()

    # Kill primary engine
    adapter.smart_fetcher._engine_health[BrowserEngine.HTTPX] = 0.0

    # Should fallback automatically
    races = await adapter.fetch_races("2026-01-27")

    # Check which engine was used
    assert adapter.smart_fetcher.last_engine != "httpx"
```

---

## 🚀 Migration Checklist

### For Each Adapter:
1. [ ] Add FetchStrategy import
2. [ ] Implement `_configure_fetch_strategy()`
3. [ ] Test with dev data
4. [ ] Verify in CI
5. [ ] Monitor health logs
6. [ ] Update tests
7. [ ] Document any quirks

### Validation:
```bash
# 1. Check adapter has strategy
grep "_configure_fetch_strategy" python_service/adapters/your_adapter.py

# 2. Run unit tests
pytest tests/test_your_adapter.py -v

# 3. Run integration test
python -m python_service.adapters.your_adapter  # If __main__ block exists

# 4. Check in CI
# Push and monitor GitHub Actions
```

---

## 📞 Troubleshooting

### "All engines failed"
1. Check browser installation: `python scripts/verify_browsers.py`
2. Check health scores: `adapter.smart_fetcher.get_health_report()`
3. Test URL manually: `curl -L "https://..."`

### "AsyncStealthySession not available"
- Camoufox not installed (optional)
- Will automatically use Playwright as backup
- To install: `pip install camoufox`

### "Timeout after 30s"
- Increase timeout: `timeout=60`
- Check if site actually loads in browser
- Consider using `page_load_strategy="domcontentloaded"`

---

**Keep this handy when updating adapters!** 📌
