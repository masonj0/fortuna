# python_service/adapters/timeform_adapter.py

import asyncio
import re
import json
from datetime import datetime, timezone
from typing import Any, List, Optional

from selectolax.parser import HTMLParser, Node

from ..models import Race, Runner, OddsData
from ..utils.odds import parse_odds_to_decimal, SmartOddsExtractor
from ..utils.text import clean_text, normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3
from .mixins import BrowserHeadersMixin, DebugMixin, JSONParsingMixin
from .utils.odds_validator import create_odds_data
from ..core.smart_fetcher import BrowserEngine, FetchStrategy


class TimeformAdapter(JSONParsingMixin, BrowserHeadersMixin, DebugMixin, BaseAdapterV3):
    """
    Adapter for timeform.com, migrated to BaseAdapterV3 and standardized on selectolax.
    """

    SOURCE_NAME = "Timeform"
    BASE_URL = "https://www.timeform.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)
        self._semaphore = asyncio.Semaphore(5)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """Timeform works with HTTPX and good headers."""
        return FetchStrategy(primary_engine=BrowserEngine.CURL_CFFI, enable_js=False)

    def _get_headers(self) -> dict:
        headers = self._get_browser_headers(host="www.timeform.com")
        headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        })
        return headers

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all race pages for a given date.
        """
        index_url = f"/horse-racing/racecards/{date}"
        index_response = await self.make_request("GET", index_url, headers=self._get_headers())
        if not index_response or not index_response.text:
            self.logger.warning("Failed to fetch Timeform index page", url=index_url)
            return None

        self._save_debug_snapshot(index_response.text, f"timeform_index_{date}")

        parser = HTMLParser(index_response.text)
        # Updated selector for race links
        links = {a.attributes["href"] for a in parser.css("a[href*='/racecards/'][href*='/20']") if a.attributes.get("href") and not a.attributes.get("href").endswith("/racecards")}

        async def fetch_single_html(url_path: str):
            async with self._semaphore:
                await asyncio.sleep(0.5)
                response = await self.make_request("GET", url_path, headers=self._get_headers())
                return (url_path, response.text) if response else (url_path, "")

        self.logger.info(f"Found {len(links)} race links on Timeform")
        tasks = [fetch_single_html(link) for link in links]
        results = await asyncio.gather(*tasks)
        return {"pages": [r for r in results if r[1]], "date": date}

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses a list of raw HTML strings into Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        try:
            race_date = datetime.strptime(raw_data["date"], "%Y-%m-%d").date()
        except ValueError:
            self.logger.error("Invalid date format", date=raw_data.get("date"))
            return []

        all_races = []
        for url_path, html_content in raw_data["pages"]:
            if not html_content:
                continue
            try:
                parser = HTMLParser(html_content)

                # Extract via JSON-LD if possible
                venue = ""
                start_time = None
                for script in parser.css('script[type="application/ld+json"]'):
                    try:
                        data = json.loads(script.text())
                        if data.get("@type") == "Event":
                            venue = normalize_venue_name(data.get("location", {}).get("name", ""))
                            if sd := data.get("startDate"):
                                # 2026-01-28T14:32:00
                                start_time = datetime.fromisoformat(sd.split('+')[0])
                            break
                    except: continue

                if not venue:
                    # Fallback to title
                    title = parser.css_first("title")
                    if title:
                        # 14:32 DUNDALK | Races 28 January 2026 ...
                        match = re.search(r'(\d{1,2}:\d{2})\s+([^|]+)', title.text())
                        if match:
                            time_str = match.group(1)
                            venue = normalize_venue_name(match.group(2).strip())
                            start_time = datetime.combine(race_date, datetime.strptime(time_str, "%H:%M").time())

                if not venue or not start_time:
                    continue

                # Betting Forecast Parsing
                forecast_map = {}
                verdict_section = parser.css_first("section.rp-verdict")
                if verdict_section:
                    forecast_text = clean_text(verdict_section.text())
                    if "Betting Forecast :" in forecast_text:
                        # "Betting Forecast : 15/8 2.87 Spring Is Here, 3/1 4 This Guy, ..."
                        after_forecast = forecast_text.split("Betting Forecast :")[1]
                        # Split by comma
                        parts = after_forecast.split(',')
                        for part in parts:
                            # Match odds and then name
                            # Odds can be fractional space decimal
                            m = re.search(r'(\d+/\d+|EVENS)\s+([\d\.]+)?\s*(.+)', part.strip())
                            if m:
                                odds_str = m.group(1)
                                name = clean_text(m.group(3))
                                forecast_map[name.lower()] = odds_str

                # Runners
                runners = []
                # Use tbody as the main container for each runner
                for row in parser.css('tbody.rp-horse-row'):
                    if runner := self._parse_runner(row, forecast_map):
                        runners.append(runner)

                if not runners:
                    continue

                # Race number from URL or sequence
                race_number = 1
                num_match = re.search(r'/(\d+)/([^/]+)$', url_path)
                # .../1432/207/1/view... -> the '1' is the race number
                url_parts = url_path.split('/')
                if len(url_parts) >= 10:
                    try: race_number = int(url_parts[9])
                    except: pass

                race = Race(
                    id=f"tf_{venue.lower().replace(' ', '')}_{start_time:%Y%m%d}_R{race_number}",
                    venue=venue,
                    race_number=race_number,
                    start_time=start_time,
                    runners=runners,
                    source=self.source_name,
                )
                all_races.append(race)
            except Exception as e:
                self.logger.warning(f"Error parsing Timeform race: {e}")
                continue
        return all_races

    def _parse_runner(self, row: Node, forecast_map: dict = None) -> Optional[Runner]:
        """Parses a single runner from a table row node."""
        try:
            name_node = row.css_first("a.rp-horse") or row.css_first("a.rp-horseTable_horse-name")
            if not name_node:
                return None
            name = clean_text(name_node.text())

            number = 0
            num_attr = row.attributes.get("data-entrynumber")
            if num_attr:
                try:
                    number = int(num_attr)
                except:
                    pass

            if not number:
                num_node = row.css_first(".rp-entry-number") or row.css_first("span.rp-horseTable_horse-number")
                if num_node:
                    num_text = clean_text(num_node.text()).strip("()")
                    num_match = re.search(r"\d+", num_text)
                    if num_match:
                        number = int(num_match.group())

            win_odds = None
            if forecast_map and name.lower() in forecast_map:
                win_odds = parse_odds_to_decimal(forecast_map[name.lower()])

            # Try to find live odds button if available (old selector)
            if not win_odds:
                odds_tag = row.css_first("button.rp-bet-placer-btn__odds")
                if odds_tag:
                    win_odds = parse_odds_to_decimal(clean_text(odds_tag.text()))

            # Advanced heuristic fallback
            if win_odds is None:
                win_odds = SmartOddsExtractor.extract_from_node(row)

            odds_data = {}
            if win_odds:
                odds_data[self.source_name] = OddsData(win=win_odds, source=self.source_name, last_updated=datetime.now(timezone.utc))

            return Runner(number=number, name=name, odds=odds_data)
        except (AttributeError, ValueError, TypeError):
            return None
