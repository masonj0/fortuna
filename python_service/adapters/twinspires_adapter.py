"""
TwinSpires Racing Adapter with production-grade reliability.
"""

import asyncio
import os
import re
import time
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from pathlib import Path
import logging

from scrapling.parser import Selector

from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal
from .base_adapter_v3 import BaseAdapterV3

logger = logging.getLogger(__name__)


class TwinSpiresAdapter(BaseAdapterV3):
    """
    TwinSpires adapter with robust browser handling and retry logic.
    """

    SOURCE_NAME = "TwinSpires"
    BASE_URL = "https://www.twinspires.com"

    # Selector strategies (ordered by reliability)
    RACE_SELECTORS = [
        'div[class*="RaceCard"]',
        'div[class*="race-card"]',
        'section[class*="race"]',
        '[data-testid*="race"]',
        '[data-race-id]',
        'div[class*="event-card"]',
    ]

    RUNNER_SELECTORS = [
        'tr[class*="runner"]',
        'div[class*="runner"]',
        '[data-runner-id]',
        'div[class*="horse-row"]',
        'li[class*="entry"]',
    ]

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config,
            enable_cache=True,
            cache_ttl=180.0,
            rate_limit=1.5
        )
        self._session = None
        self._session_type = None
        self._debug_dir = Path(os.environ.get('DEBUG_OUTPUT_DIR', '.'))

    async def _get_session(self):
        """Get or create a browser session."""
        if self._session is not None:
            return self._session, self._session_type

        # Try StealthySession first (Camoufox)
        if os.environ.get('CAMOUFOX_AVAILABLE', 'true').lower() == 'true':
            try:
                from scrapling.fetchers import AsyncStealthySession

                self._session = AsyncStealthySession(
                    headless=True,
                    block_images=True,
                    block_webrtc=True,
                    google_search=True,
                )
                await self._session.start()
                self._session_type = "stealthy"
                self.logger.info("Using StealthySession (Camoufox)")
                return self._session, self._session_type

            except Exception as e:
                self.logger.warning(f"StealthySession failed: {e}")

        # Fallback to Playwright
        try:
            from scrapling.fetchers import AsyncStealthySession

            self._session = AsyncStealthySession(
                headless=True,
                browser_type='chromium',
            )
            await self._session.start()
            self._session_type = "playwright"
            self.logger.info("Using PlayWrightSession (Chromium)")
            return self._session, self._session_type

        except Exception as e:
            self.logger.error(f"All browser backends failed: {e}")
            raise RuntimeError("No browser backend available")

    async def _fetch_with_retry(
        self,
        url: str,
        max_retries: int = 3,
        **kwargs
    ) -> Optional[Any]:
        """Fetch with exponential backoff retry."""
        last_error = None

        for attempt in range(max_retries):
            try:
                session, _ = await self._get_session()

                if attempt > 0:
                    delay = (2 ** attempt) + random.uniform(0, 1)
                    self.logger.debug(f"Retry delay: {delay:.1f}s")
                    await asyncio.sleep(delay)

                self.logger.info(f"Fetching {url} (attempt {attempt + 1})")

                response = await session.fetch(
                    url,
                    timeout=kwargs.get('timeout', 45000),
                    network_idle=kwargs.get('network_idle', True),
                )

                if response.status == 200:
                    # Check for blocks
                    if self._is_blocked(response.text):
                        self.logger.warning("Blocked response detected")
                        last_error = "Blocked by anti-bot"
                        await self._reset_session()
                        continue

                    return response

                last_error = f"HTTP {response.status}"

            except asyncio.TimeoutError:
                last_error = "Timeout"
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Fetch error: {e}")

        self.logger.error(f"All retries failed: {last_error}")
        return None

    def _is_blocked(self, html: str) -> bool:
        """Check if response indicates blocking."""
        indicators = ['captcha', 'challenge', 'access denied', 'cf-browser']
        return any(ind in html.lower() for ind in indicators)

    async def _reset_session(self):
        """Reset the browser session."""
        if self._session:
            try:
                await self._session.close()
            except:
                pass
            self._session = None
            self._session_type = None

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """Fetch race data for the given date."""
        self.logger.info(f"Fetching TwinSpires races for {date}")

        urls = [
            f"{self.BASE_URL}/bet/todays-races/time",
            f"{self.BASE_URL}/racing/entries",
        ]

        for url in urls:
            response = await self._fetch_with_retry(url)

            if response:
                # Save debug HTML
                await self._save_debug(response.text, "twinspires")

                # Extract races
                races_data = self._extract_races(response, date)

                if races_data:
                    self.logger.info(f"Found {len(races_data)} races from {url}")
                    return {
                        "races": races_data,
                        "date": date,
                        "source": "twinspires",
                        "url": url,
                    }

        return None

    def _extract_races(self, response, date: str) -> List[dict]:
        """Extract race data from page response."""
        races = []

        # Try each selector
        for selector in self.RACE_SELECTORS:
            try:
                elements = response.css(selector)
                if elements:
                    self.logger.debug(f"Found {len(elements)} races with: {selector}")

                    for i, elem in enumerate(elements):
                        race_data = self._extract_single_race(elem, i + 1, date)
                        if race_data:
                            races.append(race_data)

                    if races:
                        return races
            except Exception as e:
                self.logger.debug(f"Selector {selector} failed: {e}")

        # No races found - return empty
        self.logger.warning("No race elements found")
        return races

    def _extract_single_race(self, elem, default_num: int, date: str) -> Optional[dict]:
        """Extract data from a single race element."""
        try:
            html = str(elem.html) if hasattr(elem, 'html') else str(elem)

            # Extract track
            track = "Unknown"
            for sel in ['[class*="track"]', 'h2', 'h3', '[class*="venue"]']:
                found = elem.css_first(sel)
                if found and hasattr(found, 'text'):
                    track = found.text.strip()
                    break

            # Extract race number
            race_num = default_num
            for sel in ['[class*="race-num"]', '[class*="number"]']:
                found = elem.css_first(sel)
                if found:
                    digits = ''.join(filter(str.isdigit, found.text))
                    if digits:
                        race_num = int(digits)
                        break

            return {
                "html": html,
                "track": track,
                "race_number": race_num,
                "date": date,
            }
        except Exception as e:
            self.logger.debug(f"Extract race error: {e}")
            return None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parse raw data into Race objects."""
        if not raw_data or "races" not in raw_data:
            return []

        date_str = raw_data.get("date", datetime.now().strftime("%Y-%m-%d"))
        parsed = []

        for race_data in raw_data["races"]:
            try:
                race = self._parse_single_race(race_data, date_str)
                if race and race.runners:
                    parsed.append(race)
            except Exception as e:
                self.logger.warning(f"Parse error: {e}")

        return parsed

    def _parse_single_race(self, race_data: dict, date_str: str) -> Optional[Race]:
        """Parse a single race."""
        html = race_data.get("html", "")
        if not html:
            return None

        page = Selector(html)

        track = race_data.get("track", "Unknown")
        race_num = race_data.get("race_number", 1)

        # Parse runners
        runners = self._parse_runners(page)

        if not runners:
            return None

        # Generate ID
        track_id = re.sub(r'[^a-z0-9]', '', track.lower())
        race_id = f"ts_{track_id}_{date_str.replace('-', '')}_R{race_num}"

        # Parse time
        start_time = self._parse_time(page, date_str)

        return Race(
            id=race_id,
            venue=track,
            race_number=race_num,
            start_time=start_time,
            discipline="Thoroughbred",
            runners=runners,
            source=self.SOURCE_NAME,
        )

    def _parse_runners(self, page) -> List[Runner]:
        """Parse runners from race HTML."""
        runners = []

        for selector in self.RUNNER_SELECTORS:
            elements = page.css(selector)
            if elements:
                for i, elem in enumerate(elements):
                    runner = self._parse_single_runner(elem, i + 1)
                    if runner:
                        runners.append(runner)

                if runners:
                    return runners

        return runners

    def _parse_single_runner(self, elem, default_num: int) -> Optional[Runner]:
        """Parse a single runner element."""
        try:
            elem_html = str(elem.html) if hasattr(elem, 'html') else str(elem)

            # Check scratched
            scratched = 'scratch' in elem_html.lower()

            # Get number
            number = default_num
            for sel in ['[class*="number"]', '[class*="program"]']:
                found = elem.css_first(sel)
                if found:
                    digits = ''.join(filter(str.isdigit, found.text))
                    if digits:
                        number = int(digits)
                        break

            # Get name
            name = None
            for sel in ['[class*="horse"]', '[class*="name"]', 'a']:
                found = elem.css_first(sel)
                if found and hasattr(found, 'text'):
                    name = found.text.strip()
                    if name and len(name) > 1:
                        break

            if not name:
                return None

            # Get odds
            odds = {}
            if not scratched:
                for sel in ['[class*="odds"]', '[class*="ml"]']:
                    found = elem.css_first(sel)
                    if found:
                        odds_text = found.text.strip()
                        win_odds = parse_odds_to_decimal(odds_text)
                        if win_odds and 1.0 < win_odds < 999:
                            odds[self.SOURCE_NAME] = OddsData(
                                win=win_odds,
                                source=self.SOURCE_NAME,
                                last_updated=datetime.now(),
                            )
                            break

            return Runner(
                number=number,
                name=name,
                scratched=scratched,
                odds=odds,
            )
        except Exception:
            return None

    def _parse_time(self, page, date_str: str) -> Optional[datetime]:
        """Parse post time from page."""
        base_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        for sel in ['time[datetime]', '[class*="post-time"]', '[class*="mtp"]']:
            elem = page.css_first(sel)
            if elem:
                # Try datetime attribute
                dt = elem.attrib.get('datetime') if hasattr(elem, 'attrib') else None
                if dt:
                    try:
                        return datetime.fromisoformat(dt.replace('Z', '+00:00'))
                    except:
                        pass

                # Try text
                text = elem.text.strip() if hasattr(elem, 'text') else ''
                if text:
                    # Handle MTP (minutes to post)
                    mtp = re.search(r'(\d+)\s*(?:min|mtp)', text, re.I)
                    if mtp:
                        return datetime.now() + timedelta(minutes=int(mtp.group(1)))

                    # Try time formats
                    for fmt in ['%I:%M %p', '%H:%M']:
                        try:
                            t = datetime.strptime(text, fmt).time()
                            return datetime.combine(base_date, t)
                        except:
                            pass

        return datetime.combine(base_date, datetime.now().time())

    async def _save_debug(self, html: str, prefix: str):
        """Save debug HTML."""
        try:
            path = self._debug_dir / f"{prefix}_debug.html"
            path.write_text(html[:500000], encoding='utf-8')  # Limit size
        except Exception as e:
            self.logger.debug(f"Failed to save debug: {e}")

    async def cleanup(self):
        """Cleanup resources."""
        await self._reset_session()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.cleanup()
