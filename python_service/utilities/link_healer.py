#!/usr/bin/env python
"""
Link Healer: Self-healing 404 recovery system for race adapters

When a racecard adapter encounters a 404, this module:
1. Identifies the problem URL and adapter
2. Crawls the homepage/domain to find alternative correct links
3. Attempts automatic URL pattern correction
4. Falls back to domain-level search if needed
5. Reports successes and failures for learning

Usage:
    from link_healer import LinkHealer
    healer = LinkHealer(adapter_name="EquibaseAdapter")
    corrected_url = await healer.heal_url(broken_url, context_data)
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any
from urllib.parse import urljoin, urlparse, parse_qs, urlencode

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HealingStrategy(Enum):
    """Strategies for healing broken links."""
    PATTERN_FIX = "pattern_fix"          # Fix common URL structure issues
    HOMEPAGE_CRAWL = "homepage_crawl"    # Crawl homepage for correct links
    DOMAIN_SEARCH = "domain_search"      # Search domain for pattern matches
    PARAMETER_ADJUST = "parameter_adjust" # Fix query parameters
    DATE_CORRECTION = "date_correction"   # Adjust date formats in URL
    FALLBACK_API = "fallback_api"        # Use alternative API endpoint


@dataclass
class HealingResult:
    """Result of a healing attempt."""
    original_url: str
    success: bool
    healed_url: Optional[str] = None
    strategy_used: Optional[HealingStrategy] = None
    error_message: str = ""
    attempts: int = 0
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_url": self.original_url,
            "healed_url": self.healed_url,
            "strategy": self.strategy_used.value if self.strategy_used else None,
            "success": self.success,
            "error": self.error_message,
            "attempts": self.attempts,
            "timestamp": self.timestamp.isoformat(),
        }


class LinkHealer:
    """Self-healing system for fixing broken 404 links in race adapters."""

    # Domain configurations for known adapters
    ADAPTER_DOMAINS = {
        "EquibaseAdapter": {
            "domain": "equibase.com",
            "homepage": "https://equibase.com",
            "patterns": [
                r"https://equibase\.com/.*?racing",
                r"https://.*?\.equibase\.com/.*?race",
            ],
            "api_endpoint": "https://equibase.com/api/v1/races",
        },
        "BrisnetAdapter": {
            "domain": "brisnet.com",
            "homepage": "https://www.brisnet.com",
            "patterns": [
                r"https://.*?\.brisnet\.com/.*?race",
            ],
            "api_endpoint": "https://www.brisnet.com/api/races",
        },
        "RacingPostAdapter": {
            "domain": "racingpost.com",
            "homepage": "https://www.racingpost.com",
            "patterns": [
                r"https://www\.racingpost\.com/.*?racing",
            ],
            "api_endpoint": "https://www.racingpost.com/api/races",
        },
        "TwinSpiresAdapter": {
            "domain": "twinspires.com",
            "homepage": "https://www.twinspires.com",
            "patterns": [
                r"https://www\.twinspires\.com/.*?racing",
            ],
            "api_endpoint": "https://www.twinspires.com/api/races",
        },
        "AtTheRacesAdapter": {
            "domain": "attheraces.com",
            "homepage": "https://www.attheraces.com",
            "patterns": [
                r"https://www\.attheraces\.com/racecard/.*",
            ],
            "api_endpoint": "https://www.attheraces.com/api/racecards",
        },
    }

    def __init__(self, adapter_name: str, timeout: int = 10, max_retries: int = 3):
        """Initialize the link healer.

        Args:
            adapter_name: Name of the adapter (e.g., "EquibaseAdapter")
            timeout: Timeout for HTTP requests in seconds
            max_retries: Maximum healing attempts per URL
        """
        self.adapter_name = adapter_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.config = self.ADAPTER_DOMAINS.get(adapter_name, {})
        self.healing_history: List[HealingResult] = []
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self._session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._session:
            await self._session.close()

    async def heal_url(self, broken_url: str, context: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Attempt to heal a broken URL.

        Args:
            broken_url: The URL that returned 404
            context: Additional context (venue, race_number, date, etc.)

        Returns:
            Corrected URL if healing succeeded, None otherwise
        """
        result = HealingResult(original_url=broken_url, success=False)
        context = context or {}

        try:
            # Try strategies in order of likelihood to succeed
            strategies = [
                (HealingStrategy.PATTERN_FIX, self._fix_url_pattern),
                (HealingStrategy.DATE_CORRECTION, self._correct_date_format),
                (HealingStrategy.PARAMETER_ADJUST, self._adjust_parameters),
                (HealingStrategy.HOMEPAGE_CRAWL, self._crawl_homepage_for_link),
                (HealingStrategy.DOMAIN_SEARCH, self._search_domain),
                (HealingStrategy.FALLBACK_API, self._try_fallback_api),
            ]

            for strategy, handler in strategies:
                result.attempts += 1
                healed = await handler(broken_url, context)

                if healed and await self._verify_url(healed):
                    result.healed_url = healed
                    result.strategy_used = strategy
                    result.success = True
                    logger.info(f"✅ Healed {broken_url} using {strategy.value}")
                    self.healing_history.append(result)
                    return healed

        except Exception as e:
            result.error_message = str(e)
            logger.error(f"Link healing failed: {e}")

        result.success = False
        self.healing_history.append(result)
        return None

    async def _fix_url_pattern(self, url: str, context: Dict[str, Any]) -> Optional[str]:
        """Fix common URL structure problems."""
        # Common issues:
        # - Double slashes
        # - Wrong protocol
        # - Trailing slashes in wrong places
        # - Missing path components

        fixed = url

        # Fix double slashes (except in protocol)
        fixed = re.sub(r'(?<!:)//+', '/', fixed)

        # Ensure HTTPS
        if fixed.startswith('http://'):
            fixed = fixed.replace('http://', 'https://', 1)

        # Try with/without trailing slash
        if await self._verify_url(fixed):
            return fixed
        if not fixed.endswith('/'):
            if await self._verify_url(fixed + '/'):
                return fixed + '/'

        return None

    async def _correct_date_format(self, url: str, context: Dict[str, Any]) -> Optional[str]:
        """Attempt to correct date format issues in URL."""
        if 'date' not in context:
            return None

        date_value = context['date']

        # Try different date formats
        # Handle if date is string or datetime
        if isinstance(date_value, str):
            try:
                date_value = datetime.fromisoformat(date_value)
            except ValueError:
                return None

        date_patterns = [
            (r'\d{4}-\d{2}-\d{2}', date_value.strftime('%Y-%m-%d')),
            (r'\d{4}/\d{2}/\d{2}', date_value.strftime('%Y/%m/%d')),
            (r'\d{2}-\d{2}-\d{4}', date_value.strftime('%m-%d-%Y')),
            (r'\d{8}', date_value.strftime('%Y%m%d')),
        ]

        for pattern, replacement in date_patterns:
            corrected = re.sub(pattern, replacement, url)
            if corrected != url and await self._verify_url(corrected):
                return corrected

        return None

    async def _adjust_parameters(self, url: str, context: Dict[str, Any]) -> Optional[str]:
        """Attempt to fix query parameters."""
        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Add or fix common parameters
        if context.get('venue'):
            params['venue'] = [context['venue']]
        if context.get('race_number'):
            params['race'] = [str(context['race_number'])]
        if context.get('date'):
            d = context['date']
            if hasattr(d, 'isoformat'):
                params['date'] = [d.isoformat()]
            else:
                params['date'] = [str(d)]

        # Reconstruct URL
        new_query = urlencode(params, doseq=True)
        corrected = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{new_query}"

        if await self._verify_url(corrected):
            return corrected

        return None

    async def _crawl_homepage_for_link(self, url: str, context: Dict[str, Any]) -> Optional[str]:
        """Crawl adapter homepage to find correct link patterns."""
        if not self.config.get('homepage'):
            return None

        try:
            homepage = self.config['homepage']
            async with self._get_session().get(
                homepage,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers=self._get_headers()
            ) as resp:
                if resp.status != 200:
                    return None

                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Look for race-related links
                race_links = []
                for link in soup.find_all('a', href=True):
                    href = link['href']

                    # Check if it matches expected patterns
                    for pattern in self.config.get('patterns', []):
                        if re.search(pattern, href):
                            race_links.append(href)

                # Try to find one matching our context
                for link in race_links:
                    full_link = urljoin(homepage, link)
                    if await self._context_matches_url(full_link, context):
                        return full_link

                # Return first matching pattern if no context match
                if race_links:
                    return urljoin(homepage, race_links[0])
                return None

        except Exception as e:
            logger.debug(f"Homepage crawl failed: {e}")
            return None

    async def _search_domain(self, url: str, context: Dict[str, Any]) -> Optional[str]:
        """Search domain for matching URL patterns."""
        if not self.config.get('domain'):
            return None

        parsed = urlparse(url)
        domain = self.config['domain']

        # Build search queries based on context
        venue = context.get('venue', 'default')
        date_val = context.get('date')
        if hasattr(date_val, 'strftime'):
            date_str = date_val.strftime('%Y%m%d')
        else:
            date_str = str(date_val)

        # Attempt common URL structures
        base = f"https://{domain}"
        attempts = [
            f"{base}/racing/{venue}/{date_str}",
            f"{base}/races/{venue}",
            f"{base}/api/races?venue={venue}&date={date_str}",
        ]

        for attempt in attempts:
            if await self._verify_url(attempt):
                return attempt

        return None

    async def _try_fallback_api(self, url: str, context: Dict[str, Any]) -> Optional[str]:
        """Try adapter's fallback API endpoint."""
        api_endpoint = self.config.get('api_endpoint')
        if not api_endpoint:
            return None

        # Try API with context parameters
        params = {}
        if context.get('venue'):
            params['venue'] = context['venue']
        if context.get('date'):
            d = context['date']
            if hasattr(d, 'isoformat'):
                params['date'] = d.isoformat()
            else:
                params['date'] = str(d)

        api_url = api_endpoint
        if params:
            api_url += '?' + urlencode(params)

        if await self._verify_url(api_url):
            return api_url

        return None

    async def _verify_url(self, url: str) -> bool:
        """Verify that a URL is accessible (returns 200 or 304, not 404/403)."""
        try:
            async with self._get_session().head(
                url,
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                allow_redirects=True,
                headers=self._get_headers()
            ) as resp:
                # 200 OK, 304 Not Modified, 3xx redirects are acceptable
                return resp.status < 400
        except Exception:
            return False

    async def _context_matches_url(self, url: str, context: Dict[str, Any]) -> bool:
        """Check if URL contains context clues."""
        if context.get('venue') and context['venue'].lower() in url.lower():
            return True
        if context.get('date'):
            d = context['date']
            if hasattr(d, 'isoformat'):
                date_str = d.isoformat()
                if date_str in url or date_str.replace('-', '') in url:
                    return True
        return False

    def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    def _get_headers(self) -> Dict[str, str]:
        """Get request headers that mimic a browser."""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }

    def get_healing_report(self) -> Dict[str, Any]:
        """Get a report of all healing attempts."""
        return {
            "adapter": self.adapter_name,
            "total_attempts": len(self.healing_history),
            "successful_heals": sum(1 for h in self.healing_history if h.success),
            "strategies_used": list(set(
                h.strategy_used.value for h in self.healing_history if h.strategy_used
            )),
            "healing_history": [h.to_dict() for h in self.healing_history],
        }


class LinkHealerPool:
    """Manages multiple link healers for different adapters."""

    def __init__(self):
        self.healers: Dict[str, LinkHealer] = {}
        self.global_history: List[HealingResult] = []

    async def heal_url(
        self,
        adapter_name: str,
        broken_url: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Heal a URL using the appropriate adapter healer."""
        if adapter_name not in self.healers:
            self.healers[adapter_name] = LinkHealer(adapter_name)

        healer = self.healers[adapter_name]
        healed = await healer.heal_url(broken_url, context)

        if healer.healing_history:
            self.global_history.append(healer.healing_history[-1])

        return healed

    def get_global_report(self) -> Dict[str, Any]:
        """Get report across all adapters."""
        return {
            "timestamp": datetime.now().isoformat(),
            "total_healing_attempts": len(self.global_history),
            "successful_heals": sum(1 for h in self.global_history if h.success),
            "by_adapter": {
                name: healer.get_healing_report()
                for name, healer in self.healers.items()
            },
        }

    async def close(self):
        """Close all healer sessions."""
        for healer in self.healers.values():
            if healer._session:
                await healer._session.close()


# Global pool instance
_pool = LinkHealerPool()


async def heal_url(
    adapter_name: str,
    broken_url: str,
    context: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """Convenience function to heal a URL."""
    return await _pool.heal_url(adapter_name, broken_url, context)


def get_healing_report() -> Dict[str, Any]:
    """Get the global healing report."""
    return _pool.get_global_report()
