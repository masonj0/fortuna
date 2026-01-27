# python_service/adapters/timeform_adapter.py

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
from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy


class TimeformAdapter(BrowserHeadersMixin, DebugMixin, BaseAdapterV3):
    """
    Adapter for timeform.com, migrated to BaseAdapterV3 and standardized on selectolax.
    """

    SOURCE_NAME = "Timeform"
    BASE_URL = "https://www.timeform.com/horse-racing"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX)

    def _get_headers(self) -> dict:
        return self._get_browser_headers(host="www.timeform.com")

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all race pages for a given date.
        """
        index_url = f"/racecards/{date}"
        index_response = await self.make_request("GET", index_url, headers=self._get_headers())
        if not index_response or not index_response.text:
            self.logger.warning("Failed to fetch Timeform index page", url=index_url)
            return None

        self._save_debug_html(index_response.text, f"timeform_index_{date}")

        parser = HTMLParser(index_response.text)
        links = {a.attributes["href"] for a in parser.css("a.rp-racecard-off-link[href]") if a.attributes.get("href")}

        async def fetch_single_html(url_path: str):
            response = await self.make_request("GET", url_path, headers=self._get_headers())
            return response.text if response else ""

        tasks = [fetch_single_html(link) for link in links]
        html_pages = await asyncio.gather(*tasks)
        return {"pages": html_pages, "date": date}

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses a list of raw HTML strings into Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        try:
            race_date = datetime.strptime(raw_data["date"], "%Y-%m-%d").date()
        except ValueError:
            self.logger.error(
                "Invalid date format provided to TimeformAdapter",
                date=raw_data.get("date"),
            )
            return []

        all_races = []
        for html in raw_data["pages"]:
            if not html:
                continue
            try:
                parser = HTMLParser(html)

                track_name_node = parser.css_first("h1.rp-raceTimeCourseName_name")
                if not track_name_node:
                    continue
                track_name = clean_text(track_name_node.text())

                race_time_node = parser.css_first("span.rp-raceTimeCourseName_time")
                if not race_time_node:
                    continue
                race_time_str = clean_text(race_time_node.text())

                start_time = datetime.combine(race_date, datetime.strptime(race_time_str, "%H:%M").time())

                all_times = [clean_text(a.text()) for a in parser.css("a.rp-racecard-off-link")]
                race_number = all_times.index(race_time_str) + 1 if race_time_str in all_times else 1

                runner_rows = parser.css("div.rp-horseTable_mainRow")
                if not runner_rows:
                    continue

                runners = [self._parse_runner(row) for row in runner_rows]
                race = Race(
                    id=f"tf_{track_name.replace(' ', '')}_{start_time.strftime('%Y%m%d')}_R{race_number}",
                    venue=track_name,
                    race_number=race_number,
                    start_time=start_time,
                    runners=[r for r in runners if r],  # Filter out None values
                    source=self.source_name,
                )
                all_races.append(race)
            except (AttributeError, ValueError, TypeError):
                self.logger.warning("Error parsing a race from Timeform, skipping race.", exc_info=True)
                continue
        return all_races

    def _parse_runner(self, row: Node) -> Optional[Runner]:
        try:
            name_node = row.css_first("a.rp-horseTable_horse-name")
            if not name_node:
                return None
            name = clean_text(name_node.text())

            num_node = row.css_first("span.rp-horseTable_horse-number")
            if not num_node:
                return None
            num_str = clean_text(num_node.text())
            number_part = "".join(filter(str.isdigit, num_str.strip("()")))
            number = int(number_part)

            odds_data = {}
            odds_tag = row.css_first("button.rp-bet-placer-btn__odds")
            if odds_tag:
                odds_str = clean_text(odds_tag.text())
                if win_odds := parse_odds_to_decimal(odds_str):
                    if odds_data_val := create_odds_data(self.source_name, win_odds):
                        odds_data[self.source_name] = odds_data_val

            return Runner(number=number, name=name, odds=odds_data)
        except (AttributeError, ValueError, TypeError):
            self.logger.warning("Failed to parse a runner from Timeform, skipping runner.")
            return None
