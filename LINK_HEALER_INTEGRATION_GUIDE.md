# LINK HEALER INTEGRATION GUIDE

Link Healer is a self-healing system designed to recover from HTTP 404 errors during race data scraping. By automatically attempting various correction strategies, it significantly improves data collection reliability.

## 🚀 Quick Start (5 Steps)

### 1. Update Dependencies
Add the following to your `requirements.txt`:
```
beautifulsoup4>=4.11.0
aiohttp>=3.8.0
```

### 2. Install the Module
Ensure `link_healer.py` is located in your `python_service/utilities/` directory.

### 3. Basic Adapter Integration
In your adapter's fetch method, wrap the 404 handling logic:

```python
from python_service.utilities.link_healer import heal_url

async def fetch_race_data(self, url, context=None):
    try:
        response = await self.make_request(url)
        if response.status_code == 404:
            # Trigger Link Healer
            healed_url = await heal_url(self.__class__.__name__, url, context)
            if healed_url:
                logger.info(f"Retrying with healed URL: {healed_url}")
                response = await self.make_request(healed_url)
        return response
    except Exception as e:
        logger.error(f"Fetch failed: {e}")
        return None
```

### 4. Capture Healing Reports
In your reporter script (e.g., `fortuna_reporter.py`), save the cumulative healing report:

```python
from python_service.utilities.link_healer import get_healing_report

# After all fetches are complete
report = get_healing_report()
with open("link_healing_report.json", "w") as f:
    json.dump(report, f, indent=2)
```

### 5. Configure GitHub Actions Artifacts
Add the report to your workflow's artifact upload step:

```yaml
- name: '📊 Upload Artifacts'
  uses: actions/upload-artifact@v4
  with:
    name: race-reports
    path: |
      qualified_races.json
      link_healing_report.json
```

## 🧠 Healing Strategies

Link Healer attempts strategies in the following order:

1.  **Pattern Fix:** Corrects double slashes, protocol mismatches, and trailing slashes.
2.  **Date Correction:** Tries multiple date formats (YYYY-MM-DD, YYYYMMDD, etc.).
3.  **Parameter Adjustment:** Fixes or adds query parameters like `venue`, `race`, and `date`.
4.  **Homepage Crawl:** Scans the site's homepage for links matching known race patterns.
5.  **Domain Search:** Attempts common URL structures based on venue and date.
6.  **Fallback API:** Uses alternative API endpoints if configured.

## 🛠️ Configuration

You can extend the system by adding new adapters to the `ADAPTER_DOMAINS` dictionary in `link_healer.py`.

```python
ADAPTER_DOMAINS = {
    "NewAdapter": {
        "domain": "example.com",
        "homepage": "https://example.com",
        "patterns": [r"https://example\.com/races/.*"],
        "api_endpoint": "https://api.example.com/v1",
    }
}
```

## 📊 Monitoring

Review `link_healing_report.json` after each run to monitor success rates and identify problematic adapters that might need manual intervention or better healing strategies.
