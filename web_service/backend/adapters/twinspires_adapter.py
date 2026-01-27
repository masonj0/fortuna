"""
TwinSpires Racing Adapter - Production Implementation

Uses Scrapling's AsyncStealthySession for anti-bot bypass with:
- Persistent session pooling
- Exponential backoff retry logic
- Comprehensive selector strategies
- Detailed diagnostics for debugging
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import re
import os
import asyncio
import logging
import random
from pathlib import Path

from scrapling.fetchers import AsyncStealthySession
from scrapling.parser import Selector

from web_service.backend.models import OddsData, Race, Runner
from web_service.backend.utils.odds import parse_odds_to_decimal
from .base_adapter_v3 import BaseAdapterV3
from python_service.browser.adaptive_selector import get_browser_selector, BrowserBackend

logger = logging.getLogger(__name__)


class TwinSpiresAdapter(BaseAdapterV3):
    """
    Production adapter for TwinSpires racing data.

    Features:
    - StealthySession with automatic Playwright fallback
    - Exponential backoff retry logic
    - Comprehensive selector strategies
    - Debug HTML capture for failure analysis
    """

    SOURCE_NAME = "TwinSpires"
    BASE_URL = "https://www.twinspires.com"

    # Selector strategies - ordered by reliability
    RACE_CONTAINER_SELECTORS = [
        'div[class*="RaceCard"]',
        'div[class*="race-card"]',
        'div[data-testid*="race"]',
        'div[data-race-id]',
        'section[class*="race"]',
        'article[class*="race"]',
        '.race-container',
        '[data-race]',
        # Broader fallbacks
        'div[class*="card"][class*="race" i]',
        'div[class*="event"]',
    ]

    TRACK_NAME_SELECTORS = [
        '[class*="track-name"]',
        '[class*="trackName"]',
        '[data-track-name]',
        'h2[class*="track"]',
        'h3[class*="track"]',
        '.track-title',
        '[class*="venue"]',
    ]

    RACE_NUMBER_SELECTORS = [
        '[class*="race-number"]',
        '[class*="raceNumber"]',
        '[class*="race-num"]',
        '[data-race-number]',
        'span[class*="number"]',
    ]

    POST_TIME_SELECTORS = [
        'time[datetime]',
        '[class*="post-time"]',
        '[class*="postTime"]',
        '[class*="mtp"]',  # Minutes to post
        '[data-post-time]',
        '[class*="race-time"]',
    ]

    RUNNER_ROW_SELECTORS = [
        'tr[class*="runner"]',
        'div[class*="runner"]',
        'li[class*="runner"]',
        '[data-runner-id]',
        'div[class*="horse-row"]',
        'tr[class*="horse"]',
        'div[class*="entry"]',
        '.runner-row',
        '.horse-entry',
    ]

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config,
            enable_cache=True,
            cache_ttl=180.0,
            rate_limit=1.5  # Slightly more conservative
        )
        self._browser_selector = get_browser_selector()
        self._sessions: Dict[BrowserBackend, Any] = {}
        self._debug_dir = Path(os.environ.get('DEBUG_OUTPUT_DIR', '.'))
        self.attempted_url: Optional[str] = None

    async def _get_session(self, backend: BrowserBackend):
        if backend not in self._sessions:
            if backend == BrowserBackend.STEALTHY_CAMOUFOX:
                self._sessions[backend] = AsyncStealthySession(headless=True, block_images=True, solve_cloudflare=True)
            elif backend == BrowserBackend.PLAYWRIGHT_CHROMIUM:
                # In newer scrapling versions, AsyncStealthySession handles all browser types
                self._sessions[backend] = AsyncStealthySession(headless=True, browser_type='chromium')
            elif backend == BrowserBackend.PLAYWRIGHT_FIREFOX:
                self._sessions[backend] = AsyncStealthySession(headless=True, browser_type='firefox')

            try:
                await self._sessions[backend].start()
            except RuntimeError as e:
                if "already has an active browser context" not in str(e):
                    raise
        return self._sessions[backend]

    async def _fetch_with_retry(
        self,
        url: str,
        max_retries: int = 3,
        base_delay: float = 2.0,
        **fetch_kwargs
    ) -> Optional[Any]:
        """
        Fetch URL with exponential backoff retry logic.

        Args:
            url: URL to fetch
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries (doubles each attempt)
            **fetch_kwargs: Additional arguments for session.fetch()

        Returns:
            Response object or None on failure
        """
        last_error = None

        for attempt in range(max_retries):
            backend = await self._browser_selector.select_backend()
            session = await self._get_session(backend)
            start_time = asyncio.get_event_loop().time()

            try:
                self.logger.info(
                    f"Fetch attempt {attempt + 1}/{max_retries} using {backend.value}",
                    url=url
                )

                # Add jitter to avoid thundering herd
                if attempt > 0:
                    delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                    self.logger.debug(f"Waiting {delay:.1f}s before retry")
                    await asyncio.sleep(delay)

                response = await session.fetch(url, **fetch_kwargs)

                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000

                # Check for soft failures (200 but blocked content)
                if response.status == 200:
                    if self._is_blocked_response(response.text):
                        self.logger.warning("Detected blocked response (CAPTCHA/Challenge)")
                        await self._browser_selector.record_result(backend, False, latency_ms, "blocked")
                        last_error = "Blocked by anti-bot"
                        continue

                    await self._browser_selector.record_result(backend, True, latency_ms)
                    return response

                elif response.status in (403, 429, 503):
                    self.logger.warning(f"Rate limited or blocked: {response.status}")
                    await self._browser_selector.record_result(backend, False, latency_ms, f"http_{response.status}")
                    last_error = f"HTTP {response.status}"
                    continue

                else:
                    self.logger.error(f"Unexpected status: {response.status}")
                    await self._browser_selector.record_result(backend, False, latency_ms, f"http_{response.status}")
                    last_error = f"HTTP {response.status}"

            except asyncio.TimeoutError:
                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                self.logger.warning(f"Timeout on attempt {attempt + 1}")
                await self._browser_selector.record_result(backend, False, latency_ms, "timeout")
                last_error = "Timeout"

            except Exception as e:
                latency_ms = (asyncio.get_event_loop().time() - start_time) * 1000
                self.logger.error(f"Fetch error: {e}", exc_info=True)
                await self._browser_selector.record_result(backend, False, latency_ms, type(e).__name__)
                last_error = str(e)

        self.logger.error(f"All {max_retries} attempts failed. Last error: {last_error}")
        return None

    def _is_blocked_response(self, html: str) -> bool:
        """Check if response indicates we're blocked."""
        blocked_indicators = [
            'captcha',
            'challenge-running',
            'cf-browser-verification',
            'access denied',
            'please verify you are a human',
            'ray id',  # CloudFlare
            'checking your browser',
        ]
        html_lower = html.lower()
        return any(indicator in html_lower for indicator in blocked_indicators)

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetch race data from TwinSpires for given date.

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            Dictionary with races data or None on failure
        """
        self.logger.info(f"Fetching TwinSpires races for {date}")

        # Try multiple URL patterns
        url_patterns = [
            f"{self.BASE_URL}/bet/todays-races/time",
            f"{self.BASE_URL}/racing/entries/{date}",
            f"{self.BASE_URL}/races/today",
        ]

        for url in url_patterns:
            self.attempted_url = url
            self.logger.info(f"Trying URL pattern: {url}")

            response = await self._fetch_with_retry(
                url,
                max_retries=int(os.environ.get('MAX_RETRIES', 3)),
                timeout=int(os.environ.get('REQUEST_TIMEOUT', 45)) * 1000,
                network_idle=True,
                wait_selector='div[class*="race"], [class*="RaceCard"], [class*="track"]',
            )

            if response and response.status == 200:
                # Save debug HTML
                await self._save_debug_html(response.text, 'twinspires')

                # Extract races
                races_data = self._extract_races_from_page(response, date)

                if races_data:
                    self.logger.info(f"Successfully extracted {len(races_data)} races from {url}")
                    return {
                        "races": races_data,
                        "date": date,
                        "source": "twinspires_live",
                        "url": url,
                    }
                else:
                    self.logger.warning(f"No races extracted from {url}, trying next pattern")

        self.logger.error("All URL patterns failed")
        return None

    def _extract_races_from_page(self, response, date: str) -> List[dict]:
        """
        Extract race information from page response.

        Uses multiple selector strategies with fallback.
        """
        races_data = []
        page = response  # Response object has Selector methods

        # Try each selector pattern
        race_elements = []
        selector_used = None

        for selector in self.RACE_CONTAINER_SELECTORS:
            try:
                elements = page.css(selector)
                if elements and len(elements) > 0:
                    # Verify these look like race containers
                    sample = elements[0]
                    sample_text = str(sample.html) if hasattr(sample, 'html') else str(sample)

                    # Quick sanity check - should have some race-like content
                    if any(kw in sample_text.lower() for kw in ['race', 'post', 'horse', 'runner', 'odds']):
                        race_elements = elements
                        selector_used = selector
                        break
            except Exception as e:
                self.logger.debug(f"Selector '{selector}' failed: {e}")
                continue

        if race_elements:
            self.logger.info(f"Found {len(race_elements)} race containers using: '{selector_used}'")
        else:
            self.logger.warning("No race containers found with any selector")
            # Return full page for further analysis
            return [{
                "html": response.text,
                "track": "Unknown",
                "race_number": 0,
                "date": date,
                "full_page": True,
            }]

        # Extract data from each race element
        for i, race_elem in enumerate(race_elements, 1):
            try:
                race_data = self._extract_single_race_data(race_elem, i, date)
                if race_data:
                    races_data.append(race_data)
            except Exception as e:
                self.logger.warning(f"Failed to extract race {i}: {e}")
                continue

        return races_data

    def _extract_single_race_data(self, race_elem, default_num: int, date: str) -> Optional[dict]:
        """Extract data from a single race element."""
        try:
            # Get HTML string
            html = str(race_elem.html) if hasattr(race_elem, 'html') else str(race_elem)

            # Extract track name
            track_name = self._find_with_selectors(race_elem, self.TRACK_NAME_SELECTORS)
            if not track_name:
                track_name = f"Track {default_num}"

            # Extract race number
            race_num_text = self._find_with_selectors(race_elem, self.RACE_NUMBER_SELECTORS)
            race_number = default_num
            if race_num_text:
                digits = ''.join(filter(str.isdigit, race_num_text))
                if digits:
                    race_number = int(digits)

            # Extract post time
            post_time_text = self._find_with_selectors(race_elem, self.POST_TIME_SELECTORS)

            return {
                "html": html,
                "track": track_name.strip(),
                "race_number": race_number,
                "post_time_text": post_time_text,
                "date": date,
                "full_page": False,
            }

        except Exception as e:
            self.logger.debug(f"Extract single race error: {e}")
            return None

    def _find_with_selectors(self, element, selectors: List[str]) -> Optional[str]:
        """Try multiple selectors and return first matching text."""
        for selector in selectors:
            try:
                found = element.css_first(selector)
                if found:
                    text = found.text.strip() if hasattr(found, 'text') else str(found).strip()
                    if text:
                        return text
            except Exception:
                continue
        return None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parse extracted race data into Race objects."""
        if not raw_data or "races" not in raw_data:
            self.logger.warning("No races data to parse")
            return []

        races_list = raw_data["races"]
        date_str = raw_data.get("date", datetime.now().strftime("%Y-%m-%d"))

        self.logger.info(f"Parsing {len(races_list)} races")

        parsed_races = []

        for race_data in races_list:
            try:
                race = self._parse_single_race(race_data, date_str)
                if race and race.runners:
                    parsed_races.append(race)
                    self.logger.debug(
                        f"Parsed race",
                        track=race.venue,
                        race=race.race_number,
                        runners=len(race.runners)
                    )
            except Exception as e:
                self.logger.warning(
                    f"Failed to parse race",
                    track=race_data.get("track"),
                    error=str(e),
                    exc_info=True
                )
                continue

        self.logger.info(f"Successfully parsed {len(parsed_races)} races with runners")
        return parsed_races

    def _parse_single_race(self, race_data: dict, date_str: str) -> Optional[Race]:
        """Parse a single race from extracted data."""
        html = race_data.get("html", "")
        if not html:
            return None

        page = Selector(html)

        track_name = race_data.get("track", "Unknown")
        race_number = race_data.get("race_number", 1)

        # Parse start time
        start_time = self._parse_post_time(
            race_data.get("post_time_text"),
            page,
            date_str
        )

        # Parse runners
        runners = self._parse_runners(page)

        # Generate race ID
        track_id = re.sub(r'[^a-z0-9]', '', track_name.lower())
        date_compact = date_str.replace('-', '')
        race_id = f"ts_{track_id}_{date_compact}_R{race_number}"

        # Determine discipline
        discipline = self._detect_discipline(page, html)

        return Race(
            id=race_id,
            venue=track_name,
            race_number=race_number,
            start_time=start_time,
            discipline=discipline,
            runners=runners,
            source=self.SOURCE_NAME,
        )

    def _parse_post_time(
        self,
        time_text: Optional[str],
        page,
        date_str: str
    ) -> Optional[datetime]:
        """Parse post time from text or page elements."""
        base_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        # Try provided time text first
        if time_text:
            parsed = self._parse_time_string(time_text, base_date)
            if parsed:
                return parsed

        # Try finding time in page
        for selector in self.POST_TIME_SELECTORS:
            elem = page.css_first(selector)
            if not elem:
                continue

            # Check datetime attribute
            dt_attr = elem.attrib.get('datetime') if hasattr(elem, 'attrib') else None
            if dt_attr:
                try:
                    return datetime.fromisoformat(dt_attr.replace('Z', '+00:00'))
                except ValueError:
                    pass

            # Try text content
            text = elem.text.strip() if hasattr(elem, 'text') else str(elem).strip()
            parsed = self._parse_time_string(text, base_date)
            if parsed:
                return parsed

        # Default to now + 1 hour if nothing found
        self.logger.debug("Could not determine post time, using default")
        return datetime.combine(base_date, datetime.now().time()) + timedelta(hours=1)

    def _parse_time_string(self, time_str: str, base_date) -> Optional[datetime]:
        """Parse various time string formats."""
        if not time_str:
            return None

        # Clean up string
        time_clean = re.sub(r'\s+(EST|EDT|CST|CDT|MST|MDT|PST|PDT|ET|PT|CT|MT)$', '', time_str, flags=re.I)
        time_clean = time_clean.strip()

        # Handle "MTP" (minutes to post) format
        mtp_match = re.search(r'(\d+)\s*(?:min|mtp)', time_clean, re.I)
        if mtp_match:
            minutes = int(mtp_match.group(1))
            return datetime.now() + timedelta(minutes=minutes)

        # Try various time formats
        formats = [
            '%I:%M %p',      # 3:45 PM
            '%I:%M%p',       # 3:45PM
            '%H:%M',         # 15:45
            '%I:%M:%S %p',   # 3:45:00 PM
        ]

        for fmt in formats:
            try:
                time_obj = datetime.strptime(time_clean, fmt).time()
                return datetime.combine(base_date, time_obj)
            except ValueError:
                continue

        return None

    def _parse_runners(self, page) -> List[Runner]:
        """Parse runner information from race HTML."""
        runners = []

        # Find runner elements
        runner_elements = []
        for selector in self.RUNNER_ROW_SELECTORS:
            try:
                elements = page.css(selector)
                if elements and len(elements) > 0:
                    runner_elements = elements
                    self.logger.debug(f"Found {len(elements)} runners with: {selector}")
                    break
            except Exception:
                continue

        if not runner_elements:
            self.logger.debug("No runner elements found")
            return runners

        for i, elem in enumerate(runner_elements):
            try:
                runner = self._parse_single_runner(elem, i + 1)
                if runner:
                    runners.append(runner)
            except Exception as e:
                self.logger.debug(f"Failed to parse runner {i + 1}: {e}")
                continue

        return runners

    def _parse_single_runner(self, elem, default_number: int) -> Optional[Runner]:
        """Parse a single runner element."""
        # Get element content
        elem_str = str(elem.html) if hasattr(elem, 'html') else str(elem)
        elem_lower = elem_str.lower()

        # Check if scratched
        scratched = any(s in elem_lower for s in ['scratched', 'scr', 'scratch'])

        # Extract program number
        number_selectors = [
            '[class*="program"]',
            '[class*="saddle"]',
            '[class*="post"]',
            '[class*="number"]',
            '[data-program-number]',
            'td:first-child',
        ]

        number = None
        for selector in number_selectors:
            try:
                num_elem = elem.css_first(selector)
                if num_elem:
                    num_text = num_elem.text.strip() if hasattr(num_elem, 'text') else str(num_elem)
                    digits = ''.join(filter(str.isdigit, num_text))
                    if digits:
                        number = int(digits)
                        break
            except Exception:
                continue

        if number is None:
            number = default_number

        # Extract horse name
        name_selectors = [
            '[class*="horse-name"]',
            '[class*="horseName"]',
            '[class*="runner-name"]',
            'a[class*="name"]',
            '[data-horse-name]',
            'td:nth-child(2)',
        ]

        name = None
        for selector in name_selectors:
            try:
                name_elem = elem.css_first(selector)
                if name_elem:
                    name_text = name_elem.text.strip() if hasattr(name_elem, 'text') else None
                    if name_text and len(name_text) > 1:
                        # Clean up name
                        name = re.sub(r'\([^)]*\)', '', name_text).strip()
                        break
            except Exception:
                continue

        if not name:
            return None

        # Extract odds
        odds = {}
        if not scratched:
            odds_selectors = [
                '[class*="odds"]',
                '[class*="ml"]',  # Morning line
                '[class*="morning-line"]',
                '[data-odds]',
            ]

            for selector in odds_selectors:
                try:
                    odds_elem = elem.css_first(selector)
                    if odds_elem:
                        odds_text = odds_elem.text.strip() if hasattr(odds_elem, 'text') else None
                        if odds_text and odds_text.upper() not in ['SCR', 'SCRATCHED', '--', 'N/A']:
                            win_odds = parse_odds_to_decimal(odds_text)
                            if win_odds and 1.0 < win_odds < 999:
                                odds[self.SOURCE_NAME] = OddsData(
                                    win=win_odds,
                                    source=self.SOURCE_NAME,
                                    last_updated=datetime.now(),
                                )
                                break
                except Exception:
                    continue

        return Runner(
            number=number,
            name=name,
            scratched=scratched,
            odds=odds,
        )

    def _detect_discipline(self, page, html: str) -> str:
        """Detect race discipline (Thoroughbred, Harness, etc)."""
        html_lower = html.lower()

        if any(kw in html_lower for kw in ['harness', 'trotter', 'pacer', 'standardbred']):
            return "Harness"
        elif any(kw in html_lower for kw in ['quarter horse', 'quarterhorse']):
            return "Quarter Horse"
        elif any(kw in html_lower for kw in ['greyhound', 'dog']):
            return "Greyhound"

        # Try finding breed element
        breed_selectors = ['[class*="breed"]', '[class*="type"]', '[data-breed]']
        for selector in breed_selectors:
            try:
                elem = page.css_first(selector)
                if elem:
                    text = elem.text.strip().lower() if hasattr(elem, 'text') else ''
                    if 'harness' in text:
                        return "Harness"
                    elif 'quarter' in text:
                        return "Quarter Horse"
            except Exception:
                continue

        return "Thoroughbred"

    async def _save_debug_html(self, html: str, prefix: str):
        """Save HTML for debugging purposes."""
        try:
            debug_file = self._debug_dir / f"{prefix}_debug.html"
            debug_file.write_text(html, encoding='utf-8')
            self.logger.debug(f"Saved debug HTML to {debug_file}")
        except Exception as e:
            self.logger.warning(f"Failed to save debug HTML: {e}")

    async def cleanup(self):
        """Cleanup resources."""
        for session in self._sessions.values():
            try:
                await session.close()
            except Exception as e:
                self.logger.warning(f"Error closing session: {e}")
        self._sessions.clear()
        self.logger.info("TwinSpires adapter cleaned up")

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
