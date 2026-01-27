# python_service/adapters/constants.py
"""Shared constants for all adapters."""

from typing import Final

# Odds thresholds
MAX_VALID_ODDS: Final[float] = 999.0
MIN_VALID_ODDS: Final[float] = 1.01

# Common HTTP headers for browser-like requests
DEFAULT_BROWSER_HEADERS: Final[dict] = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

CHROME_USER_AGENT: Final[str] = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)

CHROME_SEC_CH_UA: Final[str] = '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"'
