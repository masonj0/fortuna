"""
Link Healer - Self-healing utility for racing adapter URLs.

Recover from 404s by:
1. Fixing common pattern errors (slashes, case).
2. Rotating dates (today/tomorrow/yesterday).
3. Searching the homepage/index for current links.
"""

import re
import httpx
import structlog
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = structlog.get_logger(__name__)

async def heal_url(adapter_name: str, url: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """
    Attempts to find a functional replacement for a 404 URL.
    """
    context = context or {}
    logger.info("Attempting to heal URL", adapter=adapter_name, url=url)

    # Strategy 1: Pattern-based healing (Fixing slashes and extensions)
    healed = _heal_by_pattern(url)
    if healed:
        return healed

    # Strategy 2: Date-based healing (Check if the source uses a different date format or day)
    date_val = context.get('date')
    if date_val:
        healed = await _heal_by_date(adapter_name, url, date_val)
        if healed:
            return healed

    # Strategy 3: Index-based healing (Search the homepage for a valid link)
    healed = await _heal_by_index(adapter_name, url)
    if healed:
        return healed

    return None

def get_healing_report() -> Dict[str, Any]:
    """Returns a global healing report (placeholder for now)."""
    return {"status": "active", "healed_count": 0}

class LinkHealer:
    """Context manager and helper for link healing."""
    def __init__(self, adapter_name: str):
        self.adapter_name = adapter_name
        self.history = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    async def heal_url(self, url: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        res = await heal_url(self.adapter_name, url, context)
        if res:
            self.history.append({
                "original": url,
                "healed": res,
                "timestamp": datetime.now().isoformat()
            })
        return res

    def get_healing_report(self) -> Dict[str, Any]:
        return {
            "adapter": self.adapter_name,
            "history": self.history,
            "success_count": len(self.history)
        }

def _heal_by_pattern(url: str) -> Optional[str]:
    """Fix common URL structure issues."""
    # Remove trailing .html if it might be an API
    if url.endswith(".html") and "api" in url.lower():
        return url[:-5]

    # Ensure date formats in URL have dashes if missing
    # Example: /20240101 -> /2024-01-01
    date_match = re.search(r'/(\d{4})(\d{2})(\d{2})(/|$)', url)
    if date_match:
        fixed_date = f"/{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}"
        return url.replace(date_match.group(0), fixed_date)

    return None

async def _heal_by_date(adapter_name: str, url: str, current_date: str) -> Optional[str]:
    """Try rotating dates if the source is one day ahead/behind."""
    try:
        dt = datetime.strptime(current_date, "%Y-%m-%d")
        for delta in [1, -1]: # Try tomorrow, then yesterday
            alt_date = (dt + timedelta(days=delta)).strftime("%Y-%m-%d")
            alt_url = url.replace(current_date, alt_date)

            if alt_url != url:
                async with httpx.AsyncClient(timeout=5) as client:
                    resp = await client.head(alt_url, follow_redirects=True)
                    if resp.status_code == 200:
                        return alt_url
    except Exception:
        pass
    return None

async def _heal_by_index(adapter_name: str, url: str) -> Optional[str]:
    """Crawl the base domain or index page to find where the link went."""
    try:
        # Extract base domain
        match = re.match(r'(https?://[^/]+)', url)
        if not match:
            return None

        base_url = match.group(1)
        index_url = f"{base_url}/racecards" # Common index pattern

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(index_url, follow_redirects=True)
            if resp.status_code == 200:
                # Look for links that share part of the original URL's fingerprint
                # (e.g., the track name or race ID)
                fingerprint = url.split('/')[-1].split('?')[0]
                if len(fingerprint) > 4:
                    links = re.findall(r'href=["\']([^"\']+' + re.escape(fingerprint) + r'[^"\']*)["\']', resp.text)
                    if links:
                        found_link = links[0]
                        if not found_link.startswith("http"):
                            found_link = f"{base_url.rstrip('/')}/{found_link.lstrip('/')}"
                        return found_link
    except Exception:
        pass
    return None
