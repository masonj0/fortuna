"""
TwinSpires Racing Adapter - Production Implementation

Uses Scrapling's AsyncStealthySession for anti-bot bypass with:
- Persistent session pooling
- Exponential backoff retry logic
- Comprehensive selector strategies
- Detailed diagnostics for debugging
"""

import asyncio
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from scrapling.parser import Selector

from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal, SmartOddsExtractor
from ..utils.text import normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3
from .constants import MAX_VALID_ODDS
from .mixins import DebugMixin
from .utils.odds_validator import create_odds_data
from ..core.smart_fetcher import BrowserEngine, FetchStrategy, StealthMode
from ..utils.odds import SmartOddsExtractor

logger = logging.getLogger(__name__)


class TwinSpiresAdapter(DebugMixin, BaseAdapterV3):
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
        self.attempted_url: Optional[str] = None

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """
        TwinSpires has strong anti-bot protections.
        Using CAMOUFLAGE stealth mode and blocking non-essential resources.
        """
        return FetchStrategy(
            primary_engine=BrowserEngine.CAMOUFOX,
            enable_js=True,
            stealth_mode=StealthMode.CAMOUFLAGE,
            block_resources=True,
            max_retries=3,
            timeout=45,
        )

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetch race data from TwinSpires for given date, including multiple disciplines.
        """
        self.logger.info(f"Fetching TwinSpires multi-discipline races for {date}")

        all_races_data = []

        # We explicitly target each discipline to "force" all three as requested
        disciplines = ["thoroughbred", "harness", "greyhound"]

        for disc in disciplines:
            url = f"{self.BASE_URL}/bet/todays-races/{disc}"
            self.attempted_url = url
            self.logger.info(f"Fetching discipline: {disc} from {url}")

            try:
                response = await self.make_request(
                    "GET",
                    url,
                    network_idle=True,
                    wait_selector='div[class*="race"], [class*="RaceCard"], [class*="track"]',
                )
                if response and response.status == 200:
                    self._save_debug_snapshot(response.text, f'twinspires_{disc}_{date}')
                    disc_races = self._extract_races_from_page(response, date)
                    if disc_races:
                        # Tag them with discipline to help _detect_discipline if needed
                        for r in disc_races:
                            r["assigned_discipline"] = disc.capitalize()
                        all_races_data.extend(disc_races)
                        self.logger.info(f"Extracted {len(disc_races)} {disc} races")
            except Exception as e:
                self.logger.warning(f"Failed to fetch {disc} races: {e}")

        # If direct discipline links failed or returned nothing, try the general timeline view
        if not all_races_data:
            url = f"{self.BASE_URL}/bet/todays-races/time"
            self.logger.info(f"Falling back to timeline view: {url}")
            try:
                response = await self.make_request("GET", url, network_idle=True)
                if response and response.status == 200:
                    all_races_data = self._extract_races_from_page(response, date)
            except Exception as e:
                self.logger.warning(f"Fallback failed: {e}")

        if all_races_data:
            return {
                "races": all_races_data,
                "date": date,
                "source": self.source_name,
            }

        return None

    def _extract_races_from_page(self, response, date: str) -> List[dict]:
        """
        Extract race information from page response.

        Uses multiple selector strategies with fallback.
        """
        races_data = []
        page = Selector(response.text)

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
            html_str = str(race_elem.html) if hasattr(race_elem, 'html') else str(race_elem)

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

            # Capture available bets
            available_bets = []
            html_lower = html_str.lower()
            for kw in ["superfecta", "trifecta", "exacta", "quinella"]:
                if kw in html_lower:
                    available_bets.append(kw.capitalize())

            return {
                "html": html_str,
                "track": track_name.strip(),
                "race_number": race_number,
                "post_time_text": post_time_text,
                "date": date,
                "full_page": False,
                "available_bets": available_bets,
                "distance": self._find_with_selectors(race_elem, ['[class*="distance"]', '[class*="Distance"]', '[data-distance]', ".race-distance"])
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
        html_content = race_data.get("html", "")
        if not html_content:
            return None

        page = Selector(html_content)

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

        # Determine discipline
        discipline = race_data.get("assigned_discipline") or self._detect_discipline(page, html_content)

        # Generate race ID
        track_id = re.sub(r'[^a-z0-9]', '', track_name.lower())
        date_compact = date_str.replace('-', '')
        disc_suffix = ""
        if discipline:
            dl = discipline.lower()
            if "harness" in dl: disc_suffix = "_h"
            elif "greyhound" in dl: disc_suffix = "_g"
            elif "quarter" in dl: disc_suffix = "_q"

        race_id = f"ts_{track_id}_{date_compact}_R{race_number}{disc_suffix}"

        return Race(
            id=race_id,
            venue=track_name,
            race_number=race_number,
            start_time=start_time,
            discipline=discipline,
            runners=runners,
            source=self.source_name,
            distance=race_data.get("distance"),
            metadata={"available_bets": race_data.get("available_bets", [])}
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
                            if win_odds:
                                break
                except Exception:
                    continue

            # Advanced heuristic fallback
            if win_odds is None:
                win_odds = SmartOddsExtractor.extract_from_node(elem)

            if win_odds:
                odds[self.source_name] = OddsData(win=win_odds, source=self.source_name, last_updated=datetime.now(timezone.utc))

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

    async def cleanup(self):
        """Cleanup resources."""
        await self.close()
        self.logger.info("TwinSpires adapter cleaned up")
