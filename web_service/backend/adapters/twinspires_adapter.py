# python_service/adapters/twinspires_adapter.py
"""
TwinSpires Adapter using Scrapling's StealthyFetcher

TwinSpires is a heavily JavaScript-rendered site that requires:
- Full browser automation (not simple HTTP requests)
- Anti-bot detection bypass
- Wait for dynamic content to load

This adapter uses Scrapling's StealthyFetcher with modified Firefox.
"""

from datetime import datetime, timedelta
from typing import Any, List, Optional
import re
import os
import asyncio
import logging

from scrapling.fetchers import StealthySession
from scrapling.parser import Selector

from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal
from .base_adapter_v3 import BaseAdapterV3

logger = logging.getLogger(__name__)


class TwinSpiresAdapter(BaseAdapterV3):
    """
    Production adapter for twinspires.com using Scrapling.

    TwinSpires uses heavy JavaScript rendering, so we need:
    - Browser automation (DynamicFetcher/StealthyFetcher)
    - Wait for network idle
    - Wait for specific elements to load
    """

    SOURCE_NAME = "TwinSpires"
    BASE_URL = "https://www.twinspires.com"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config,
            enable_cache=True,
            cache_ttl=180.0,  # 3 minute cache (races change frequently)
            rate_limit=2.0    # Slower rate limit for browser automation
        )

    async def _get_session(self, retries=3):
        """
        Create and initialize a browser session with retries.
        This includes launching the browser and verifying the context.
        """
        for i in range(retries):
            session = None
            try:
                logger.info(f"Attempting to launch browser (attempt {i+1}/{retries})...")
                session = StealthySession(headless=True)
                await session.__aenter__()  # Explicitly launch the browser
                if session.context:
                    logger.info("✅ Browser context initialized successfully")
                    return session  # Success, return the active session
                else:
                    logger.warning("Browser context is None after launch.")
                    await session.close() # Clean up the failed session
            except Exception as e:
                logger.warning(f"Browser launch failed (attempt {i+1}/{retries}): {e}")
                if session:
                    await session.close() # Ensure cleanup on failure
                if i < retries - 1:
                    await asyncio.sleep(2 * (i + 1)) # Exponential backoff

        logger.error("Failed to initialize browser after all retries.")
        return None

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches live race data from TwinSpires' dynamic JavaScript page.

        TwinSpires renders everything via JavaScript, so we need:
        1. Full browser automation
        2. Wait for network requests to complete
        3. Wait for race elements to appear in DOM

        Args:
            date: Date string in YYYY-MM-DD format

        Returns:
            Dictionary containing race data and metadata
        """
        self.logger.info(f"Fetching TwinSpires races for {date}")

        session = await self._get_session()
        if not session:
            self.logger.error("Skipping TwinSpires fetch.")
            return None

        try:
            # TwinSpires shows today's races at /bet/todays-races/time
            index_url = f"{self.BASE_URL}/bet/todays-races/time"
            self.logger.info(f"Fetching: {index_url}")
            self.attempted_url = index_url

            # Fetch with extended timeout for JS to render
            index_page = await session.fetch(
                index_url,
                network_idle=True,  # Wait for all network requests
                timeout=45000,      # 45 second timeout
                wait_selector='div[class*="race"], div[data-track], .race-card, [class*="RaceCard"]',
                page_action=lambda page: page.wait_for_timeout(3000)
            )

            if index_page.status != 200:
                self.logger.error(f"Failed to fetch index: status {index_page.status}")
                return None

            # Save debug HTML if DEBUG_ADAPTERS is set
            if os.getenv("DEBUG_ADAPTERS", "false").lower() == "true":
                try:
                    with open("twinspires_debug.html", "w", encoding="utf-8") as f:
                        f.write(index_page.text)
                    self.logger.info("Saved debug HTML to twinspires_debug.html")
                except Exception as e:
                    self.logger.warning(f"Failed to save debug HTML: {e}")

            if len(index_page.text) < 5000:
                self.logger.error(f"Page content suspiciously short ({len(index_page.text)} chars). JS may not have rendered.")
                return None

            races_data = self._extract_races_from_page(index_page, date)
            if not races_data:
                self.logger.error("No races extracted from page")
                return None

            self.logger.info(f"Extracted {len(races_data)} races from TwinSpires")

            return {
                "races": races_data,
                "date": date,
                "source": "twinspires_live"
            }

        except Exception as e:
            self.logger.error("Critical error during TwinSpires fetch", error=str(e), exc_info=True)
            return None
        finally:
            if session:
                await session.close()

    def _extract_races_from_page(self, page, date: str) -> List[dict]:
        """
        Extract race information from the main TwinSpires page.

        TwinSpires shows all races on one page, organized by track and time.
        We need to parse the structure and extract race details.

        Returns:
            List of dictionaries containing race HTML and metadata
        """
        races_data = []

        # Try multiple selector patterns to find race containers
        # These are guesses - adjust after inspecting twinspires_debug.html
        potential_selectors = [
            'div[class*="RaceCard"]',
            'div[data-race]',
            'div[class*="race-card"]',
            'div.race-container',
            'section[class*="race"]',
            '[data-testid*="race"]',
        ]

        race_elements = []
        for selector in potential_selectors:
            race_elements = page.css(selector)
            if race_elements:
                self.logger.info(f"Found {len(race_elements)} races using selector: {selector}")
                break

        if not race_elements:
            self.logger.warning("Could not find race elements with any known selector")
            # Return the full page as a single "race" for parsing
            return [{
                "html": page.text,
                "track": "Unknown",
                "race_number": 1,
                "date": date
            }]

        # Extract data from each race element
        for i, race_elem in enumerate(race_elements, 1):
            try:
                # Extract track name
                track_elem = race_elem.css_first('[class*="track"], [data-track], h2, h3')
                track_name = track_elem.text.strip() if track_elem else f"Track {i}"

                # Extract race number
                race_num_elem = race_elem.css_first('[class*="race-number"], [class*="raceNum"]')
                race_number = i  # Default
                if race_num_elem:
                    try:
                        race_number = int(''.join(filter(str.isdigit, race_num_elem.text)))
                    except ValueError:
                        pass

                races_data.append({
                    "html": str(race_elem),  # Convert element to HTML string
                    "track": track_name,
                    "race_number": race_number,
                    "date": date
                })

            except Exception as e:
                self.logger.warning(f"Failed to extract race {i}: {e}")
                continue

        return races_data

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """
        Parse extracted race data into Race objects.

        Args:
            raw_data: Dictionary with 'races' list and 'date'

        Returns:
            List of Race objects
        """
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
                if race:
                    parsed_races.append(race)
            except Exception as e:
                self.logger.warning(
                    f"Failed to parse race",
                    track=race_data.get("track"),
                    error=str(e),
                    exc_info=True
                )
                continue

        self.logger.info(f"Successfully parsed {len(parsed_races)} races")
        return parsed_races

    def _parse_single_race(self, race_data: dict, date_str: str) -> Optional[Race]:
        """
        Parse a single race from HTML.

        Args:
            race_data: Dict with 'html', 'track', 'race_number', 'date'
            date_str: Date string YYYY-MM-DD

        Returns:
            Race object or None
        """
        html = race_data.get("html", "")
        if not html:
            return None

        # Parse HTML with Scrapling
        page = Selector(html)

        # Extract track name
        track_name = race_data.get("track", "Unknown")

        # Extract race number
        race_number = race_data.get("race_number", 1)

        # Extract post time
        start_time = self._extract_post_time(page, date_str)

        # Extract discipline/race type
        discipline_elem = page.css_first('[class*="breed"], [class*="type"]')
        discipline = discipline_elem.text.strip() if discipline_elem else "Thoroughbred"

        # Parse runners
        runners = self._parse_runners(page)

        if not runners or not start_time:
            self.logger.debug(f"Skipping race due to missing runners or start time", track=track_name, race=race_number)
            return None

        # Generate race ID
        track_id = re.sub(r'[^a-z0-9]', '', track_name.lower())
        race_id = f"ts_{track_id}_{date_str.replace('-', '')}_R{race_number}"

        return Race(
            id=race_id,
            venue=track_name,
            race_number=race_number,
            start_time=start_time,
            discipline=discipline,
            runners=runners,
            source=self.SOURCE_NAME,
        )

    def _extract_post_time(self, page, date_str: str) -> Optional[datetime]:
        """
        Extract post time from race HTML.

        Args:
            page: Scrapling Selector object
            date_str: Date string YYYY-MM-DD

        Returns:
            datetime object
        """
        # Try to find time element
        time_selectors = [
            'time[datetime]',
            '[class*="post-time"]',
            '[class*="postTime"]',
            '[data-time]',
        ]

        for selector in time_selectors:
            time_elem = page.css_first(selector)
            if time_elem:
                # Try datetime attribute
                dt_attr = time_elem.attrib.get('datetime')
                if dt_attr:
                    try:
                        return datetime.fromisoformat(dt_attr.replace('Z', '+00:00'))
                    except ValueError:
                        pass

                # Try parsing text like "3:45 PM EST"
                time_text = time_elem.text.strip()
                if time_text:
                    try:
                        # Remove timezone abbreviations
                        time_clean = re.sub(r'\s+(EST|EDT|CST|CDT|MST|MDT|PST|PDT)$', '', time_text)

                        # Try parsing 12-hour format
                        for fmt in ['%I:%M %p', '%I:%M%p', '%H:%M']:
                            try:
                                time_obj = datetime.strptime(time_clean, fmt).time()
                                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                                return datetime.combine(date_obj, time_obj)
                            except ValueError:
                                continue
                    except Exception:
                        pass

        self.logger.warning("Could not determine post time")
        return None

    def _parse_runners(self, page) -> List[Runner]:
        """
        Parse runner information from race HTML.

        Args:
            page: Scrapling Selector object

        Returns:
            List of Runner objects
        """
        runners = []

        # Try multiple selector patterns for runner rows
        runner_selectors = [
            'tr[class*="runner"]',
            'div[class*="runner"]',
            'li[class*="horse"]',
            '[data-runner]',
            '.horse-entry',
        ]

        runner_elements = []
        for selector in runner_selectors:
            runner_elements = page.css(selector)
            if runner_elements:
                self.logger.debug(f"Found {len(runner_elements)} runners with: {selector}")
                break

        for elem in runner_elements:
            try:
                runner = self._parse_single_runner(elem)
                if runner:
                    runners.append(runner)
            except Exception as e:
                self.logger.debug(f"Failed to parse runner: {e}")
                continue

        return runners

    def _parse_single_runner(self, elem) -> Optional[Runner]:
        """Parse a single runner element."""
        try:
            # Check if scratched
            scratched = (
                'scratched' in str(elem.attrib.get('class', '')).lower() or
                'scr' in str(elem.attrib.get('class', '')).lower() or
                bool(elem.css_first('[class*="scratch"]'))
            )

            # Extract program number
            number_selectors = [
                '[class*="program-number"]',
                '[class*="saddle-cloth"]',
                '[class*="post-position"]',
                '[data-number]',
                'span.number',
            ]

            number = None
            for selector in number_selectors:
                num_elem = elem.css_first(selector)
                if num_elem:
                    try:
                        number = int(''.join(filter(str.isdigit, num_elem.text)))
                        break
                    except ValueError:
                        continue

            if not number:
                return None

            # Extract horse name
            name_selectors = [
                '[class*="horse-name"]',
                '[class*="horseName"]',
                'a[class*="name"]',
                '[data-horse-name]',
            ]

            name = None
            for selector in name_selectors:
                name_elem = elem.css_first(selector)
                if name_elem:
                    name = name_elem.text.strip()
                    if name:
                        break

            if not name:
                return None

            # Extract odds
            odds_selectors = [
                '[class*="odds"]',
                '[class*="morning-line"]',
                '[data-odds]',
            ]

            odds = {}
            if not scratched:
                for selector in odds_selectors:
                    odds_elem = elem.css_first(selector)
                    if odds_elem:
                        odds_str = odds_elem.text.strip()
                        if odds_str and odds_str.upper() not in ['SCR', 'SCRATCHED']:
                            win_odds = parse_odds_to_decimal(odds_str)
                            if win_odds and win_odds < 999:
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

        except Exception as e:
            self.logger.debug(f"Runner parse error: {e}")
            return None
