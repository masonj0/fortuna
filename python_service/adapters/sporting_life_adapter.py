# python_service/adapters/sporting_life_adapter.py

import asyncio
from datetime import datetime
from typing import Any, List, Optional

from selectolax.parser import HTMLParser, Node

from ..models import Race, Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text
from .base_adapter_v3 import BaseAdapterV3
from .mixins import BrowserHeadersMixin, DebugMixin
from .utils.odds_validator import create_odds_data
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy, StealthMode


class SportingLifeAdapter(BrowserHeadersMixin, DebugMixin, BaseAdapterV3):
    """
    Adapter for sportinglife.com, migrated to BaseAdapterV3.
    Standardized on selectolax for performance.
    """

    SOURCE_NAME = "SportingLife"
    BASE_URL = "https://www.sportinglife.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """
        SportingLife requires JavaScript rendering to get the race links,
        so we must use a full browser engine like Playwright.
        """
        return FetchStrategy(
            primary_engine=BrowserEngine.PLAYWRIGHT,
            enable_js=True,
            stealth_mode=StealthMode.FAST,
            block_resources=True
        )

    def _get_headers(self) -> dict:
        """Get browser-like headers for SportingLife."""
        return self._get_browser_headers(
            host="www.sportinglife.com",
            referer="https://www.sportinglife.com/racing/racecards",
        )

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all race pages for a given date.
        Returns a dictionary containing the HTML content and the date.
        """
        index_url = "/racing/racecards"  # The dated URL is causing a 307 redirect
        index_response = await self.make_request(
            "GET",
            index_url,
            headers=self._get_headers(),
            follow_redirects=True,
        )
        if not index_response:
            self.logger.warning("Failed to fetch SportingLife index page", url=index_url)
            return None

        self._save_debug_snapshot(index_response.text, f"sportinglife_index_{date}")

        parser = HTMLParser(index_response.text)
        links = {
            a.attributes["href"]
            for a in parser.css('li[class^="MeetingSummary__LineWrapper"] a[href*="/racecard/"]')
            if a.attributes.get("href")
        }

        if not links:
            self.logger.warning("No race links found on SportingLife index page", date=date)
            # Try a fallback selector
            links = {
                a.attributes["href"]
                for a in parser.css('.meeting-summary a[href*="/racecard/"]')
                if a.attributes.get("href")
            }

        if not links:
            return None

        self.logger.info(f"Found {len(links)} race links on SportingLife")

        async def fetch_single_html(url_path: str):
            response = await self.make_request("GET", url_path, headers=self._get_headers())
            return response.text if response else ""

        tasks = [fetch_single_html(link) for link in links]
        html_pages = await asyncio.gather(*tasks)
        return {"pages": [p for p in html_pages if p], "date": date}

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses a list of raw HTML strings into Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        try:
            race_date = datetime.strptime(raw_data["date"], "%Y-%m-%d").date()
        except ValueError:
            self.logger.error(
                "Invalid date format provided to SportingLifeAdapter",
                date=raw_data.get("date"),
            )
            return []

        all_races = []
        for html in raw_data["pages"]:
            if not html:
                continue
            try:
                parser = HTMLParser(html)

                header = parser.css_first('h1[class*="RacingRacecardHeader__Title"]')
                if not header:
                    self.logger.warning("Could not find race header in SportingLife page.")
                    continue

                header_text = clean_text(header.text())
                parts = header_text.split()
                if not parts:
                    continue
                race_time_str = parts[0]
                track_name = " ".join(parts[1:])

                try:
                    start_time = datetime.combine(race_date, datetime.strptime(race_time_str, "%H:%M").time())
                except ValueError:
                    continue

                race_number = 1
                nav_links = parser.css('a[class*="SubNavigation__Link"]')
                active_link = parser.css_first('a[class*="SubNavigation__Link--active"]')
                if active_link and nav_links:
                    try:
                        for idx, link in enumerate(nav_links):
                            # Compare text content or href if html comparison is too strict
                            if link.text().strip() == active_link.text().strip():
                                race_number = idx + 1
                                break
                    except Exception:
                        pass

                runners = [r for row in parser.css('div[class*="RunnerCard"]') if (r := self._parse_runner(row))]

                if not runners:
                    continue

                race = Race(
                    id=f"sl_{track_name.replace(' ', '')}_{start_time:%Y%m%d}_R{race_number}",
                    venue=track_name,
                    race_number=race_number,
                    start_time=start_time,
                    runners=runners,
                    source=self.source_name,
                )
                all_races.append(race)
            except Exception as e:
                self.logger.warning(
                    "Error parsing a race from SportingLife",
                    error=str(e),
                    exc_info=True,
                )
                continue
        return all_races

    def _parse_runner(self, row: Node) -> Optional[Runner]:
        try:
            name_node = row.css_first('a[href*="/racing/profiles/horse/"]')
            if not name_node:
                return None
            name = clean_text(name_node.text()).splitlines()[0].strip()

            num_node = row.css_first('span[class*="SaddleCloth__Number"]')
            if not num_node:
                return None
            num_str = clean_text(num_node.text())
            number = int("".join(filter(str.isdigit, num_str)))

            odds_node = row.css_first('span[class*="Odds__Price"]')
            odds_str = clean_text(odds_node.text()) if odds_node else ""

            win_odds = parse_odds_to_decimal(odds_str)
            odds_data = {}
            if odds_val := create_odds_data(self.source_name, win_odds):
                odds_data[self.source_name] = odds_val

            return Runner(number=number, name=name, odds=odds_data)
        except (AttributeError, ValueError):
            return None
