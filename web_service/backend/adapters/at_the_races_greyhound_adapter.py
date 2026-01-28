# python_service/adapters/at_the_races_greyhound_adapter.py
"""Adapter for AtTheRaces Greyhound racing."""

import asyncio
import json
import re
import html
from datetime import datetime
from typing import Any, List, Optional

from selectolax.parser import HTMLParser

from ..models import Race, Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text, normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3
from .mixins import BrowserHeadersMixin, DebugMixin
from .utils.odds_validator import create_odds_data
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy


class AtTheRacesGreyhoundAdapter(BrowserHeadersMixin, DebugMixin, BaseAdapterV3):
    """
    Adapter for greyhounds.attheraces.com.

    This site is a modern SPA with data embedded in JSON-LD and HTML attributes.
    Uses simple HTTP requests as the data is available in the initial HTML.
    """

    SOURCE_NAME = "AtTheRacesGreyhound"
    BASE_URL = "https://greyhounds.attheraces.com"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config
        )
        self._semaphore = asyncio.Semaphore(5)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """Greyhounds ATR is a modern site but data is in HTML - HTTPX works."""
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX, enable_js=False)

    def _get_headers(self) -> dict:
        """Get headers for ATR Greyhound requests."""
        return self._get_browser_headers(
            host="greyhounds.attheraces.com",
            referer="https://greyhounds.attheraces.com/racecards",
        )

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """Fetch greyhound race pages for a given date."""
        # The index page contains JSON-LD with all races for today
        index_url = f"/racecards/{date}" if date else "/racecards"

        try:
            index_response = await self.make_request(
                "GET", index_url, headers=self._get_headers()
            )
        except Exception as e:
            self.logger.error(
                "Failed to fetch AtTheRaces Greyhound index page", url=index_url, error=str(e)
            )
            return None

        if not index_response:
            return None

        self._save_debug_snapshot(index_response.text, f"atr_grey_index_{date}")

        parser = HTMLParser(index_response.text)
        links = self._extract_links_from_json_ld(parser)

        if not links:
            self.logger.warning("No greyhound race links found on index page", date=date)
            return None

        self.logger.info(f"Found {len(links)} greyhound race links for {date}")

        pages = await self._fetch_race_pages(links)
        return {"pages": pages, "date": date}

    def _extract_links_from_json_ld(self, parser: HTMLParser) -> List[str]:
        """Extract race links from application/ld+json script tags."""
        links = []
        for script in parser.css('script[type="application/ld+json"]'):
            try:
                data = json.loads(script.text())
                # Handle both single object and @graph array
                items = data.get("@graph", [data]) if isinstance(data, dict) else []
                for item in items:
                    if item.get("@type") == "SportsEvent":
                        location = item.get("location")
                        if isinstance(location, list):
                            for loc in location:
                                if url := loc.get("url"):
                                    links.append(url)
                        elif isinstance(location, dict):
                            if url := location.get("url"):
                                links.append(url)
            except (json.JSONDecodeError, TypeError):
                continue
        return list(set(links))

    async def _fetch_race_pages(self, links: List[str]) -> List[tuple]:
        """Fetch all race pages concurrently with semaphore limit."""
        async def fetch_single(url_path: str):
            async with self._semaphore:
                try:
                    # Small delay to be polite
                    await asyncio.sleep(0.5)
                    response = await self.make_request(
                        "GET", url_path, headers=self._get_headers()
                    )
                    return (url_path, response.text) if response else (url_path, "")
                except Exception as e:
                    self.logger.warning(f"Failed to fetch {url_path}: {e}")
                    return (url_path, "")

        tasks = [fetch_single(link) for link in links]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            page for page in results
            if not isinstance(page, Exception) and page and page[1]
        ]

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parse greyhound race pages into Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        date_str = raw_data["date"]
        try:
            race_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            race_date = datetime.now().date()

        races = []
        for url_path, html_content in raw_data["pages"]:
            if not html_content:
                continue

            try:
                if race := self._parse_single_race(html_content, url_path, race_date):
                    races.append(race)
            except Exception as e:
                self.logger.warning("Error parsing greyhound race", url=url_path, error=str(e))
                continue

        return races

    def _parse_single_race(self, html_content: str, url_path: str, race_date) -> Optional[Race]:
        """Parse a single greyhound race from HTML content."""
        parser = HTMLParser(html_content)

        # Data is embedded in <page-content :items="..."> or :modules="..."
        page_content = parser.css_first("page-content")
        if not page_content:
            return None

        items_raw = page_content.attributes.get(":items") or page_content.attributes.get(":modules")
        if not items_raw:
            return None

        try:
            modules = json.loads(html.unescape(items_raw))
        except json.JSONDecodeError:
            return None

        # Extract race info and runners
        venue = ""
        race_time_str = ""
        runners = []
        odds_map = {}

        # Usually first module is RacecardHero or similar
        for module in modules:
            m_type = module.get("type")
            m_data = module.get("data", {})

            if m_type == "RacecardHero":
                venue = normalize_venue_name(m_data.get("track", ""))
                race_time_str = m_data.get("time", "")

            if m_type == "OddsGrid":
                odds_grid = m_data.get("oddsGrid", {})

                # Build odds map: greyhoundId -> decimal odds
                partners = odds_grid.get("partners", {})
                # Check premium partners first (usually contains bet365, etc.)
                all_partners = []
                if isinstance(partners, dict):
                    for p_list in partners.values():
                        if isinstance(p_list, list):
                            all_partners.extend(p_list)
                elif isinstance(partners, list):
                    all_partners = partners

                for partner in all_partners:
                    p_odds = partner.get("odds", [])
                    for o in p_odds:
                        g_id = o.get("betParams", {}).get("greyhoundId")
                        price = o.get("value", {}).get("decimal")
                        if g_id and price and g_id not in odds_map:
                            try:
                                odds_map[str(g_id)] = float(price)
                            except ValueError:
                                pass

                # Extract runner basic info (trap, name, id)
                traps = odds_grid.get("traps", [])
                for t in traps:
                    trap_num = t.get("trap")
                    name = clean_text(t.get("name", ""))
                    href = t.get("href", "")
                    # Extract ID from href: /stats-hub/greyhound/20431/tommys-dolly
                    g_id_match = re.search(r'/greyhound/(\d+)', href)
                    g_id = g_id_match.group(1) if g_id_match else None

                    win_odds = odds_map.get(str(g_id)) if g_id else None

                    odds_data = {}
                    if odds_val := create_odds_data(self.source_name, win_odds):
                        odds_data[self.source_name] = odds_val

                    runners.append(Runner(
                        number=trap_num or 0,
                        name=name,
                        odds=odds_data
                    ))

        if not venue or not runners:
            # Fallback for venue/time from URL if Hero missing
            # /racecard/GB/doncaster/28-January-2026/1433
            url_parts = url_path.split('/')
            if len(url_parts) >= 5:
                venue = normalize_venue_name(url_parts[3])
                race_time_str = url_parts[-1]

        if not venue or not runners:
            return None

        try:
            # Handle time format HHmm or HH:mm
            if ":" not in race_time_str and len(race_time_str) == 4:
                race_time_str = f"{race_time_str[:2]}:{race_time_str[2:]}"

            start_time = datetime.combine(
                race_date,
                datetime.strptime(race_time_str, "%H:%M").time()
            )
        except (ValueError, TypeError):
            return None

        race_id = f"atrg_{venue.lower().replace(' ', '')}_{start_time:%Y%m%d_%H%M}"

        return Race(
            id=race_id,
            venue=venue,
            race_number=0, # Greyhound cards usually don't have a simple race number in the same way
            start_time=start_time,
            runners=runners,
            source=self.source_name,
        )
