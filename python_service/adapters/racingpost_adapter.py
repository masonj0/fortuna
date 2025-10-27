# python_service/adapters/racingpost_adapter.py
import asyncio
from datetime import datetime
from typing import Any, List

from selectolax.parser import HTMLParser

from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text, normalize_venue_name
from .base_v3 import BaseAdapterV3


class RacingPostAdapter(BaseAdapterV3):
    """
    Adapter for scraping Racing Post racecards, migrated to BaseAdapterV3.
    """
    SOURCE_NAME = "RacingPost"
    BASE_URL = "https://www.racingpost.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Any:
        """
        Fetches the raw HTML content for all races on a given date.
        """
        index_url = f"/racecards/{date}"
        index_response = await self.make_request(self.http_client, "GET", index_url, headers=self._get_headers())
        if not index_response:
            self.logger.warning("Failed to fetch RacingPost index page", url=index_url)
            return None

        index_parser = HTMLParser(index_response.text)
        links = index_parser.css('a[data-test-selector^="RC-meetingItem__link_race"]')
        race_card_urls = [link.attributes['href'] for link in links]

        async def fetch_single_html(url: str):
            response = await self.make_request(self.http_client, "GET", url, headers=self._get_headers())
            return response.text if response else ""

        tasks = [fetch_single_html(url) for url in race_card_urls]
        html_contents = await asyncio.gather(*tasks)
        return {"date": date, "html_contents": html_contents}

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses a list of raw HTML strings into Race objects."""
        if not raw_data or not raw_data.get("html_contents"):
            return []

        date = raw_data["date"]
        html_contents = raw_data["html_contents"]
        all_races: List[Race] = []

        for html in html_contents:
            if not html:
                continue
            try:
                parser = HTMLParser(html)
                venue_raw = parser.css_first('a[data-test-selector="RC-course__name"]').text(strip=True)
                venue = normalize_venue_name(venue_raw)
                race_time_str = parser.css_first('span[data-test-selector="RC-course__time"]').text(strip=True)
                race_datetime_str = f"{date} {race_time_str}"
                start_time = datetime.strptime(race_datetime_str, "%Y-%m-%d %H:%M")
                runners = self._parse_runners(parser)

                if venue and runners:
                    race_number = self._get_race_number(parser, start_time)
                    race = Race(
                        id=f"rp_{venue.lower().replace(' ', '')}_{date}_{race_number}",
                        venue=venue,
                        race_number=race_number,
                        start_time=start_time,
                        runners=runners,
                        source=self.source_name,
                    )
                    all_races.append(race)
            except (AttributeError, ValueError):
                self.logger.error("Failed to parse RacingPost race from HTML content.", exc_info=True)
                continue
        return all_races

    def _get_race_number(self, parser: HTMLParser, start_time: datetime) -> int:
        """Derives the race number by finding the active time in the nav bar."""
        time_str_to_find = start_time.strftime("%H:%M")
        time_links = parser.css('a[data-test-selector="RC-raceTime"]')
        for i, link in enumerate(time_links):
            if link.text(strip=True) == time_str_to_find:
                return i + 1
        return 1

    def _parse_runners(self, parser: HTMLParser) -> list[Runner]:
        """Parses all runners from a single race card page."""
        runners = []
        runner_nodes = parser.css('div[data-test-selector="RC-runnerCard"]')
        for node in runner_nodes:
            try:
                number_node = node.css_first('span[data-test-selector="RC-runnerNumber"]')
                name_node = node.css_first('a[data-test-selector="RC-runnerName"]')
                odds_node = node.css_first('span[data-test-selector="RC-runnerPrice"]')

                if not all([number_node, name_node, odds_node]):
                    continue

                number_str = clean_text(number_node.text())
                number = int(number_str) if number_str and number_str.isdigit() else 0
                name = clean_text(name_node.text())
                odds_str = clean_text(odds_node.text())
                scratched = "NR" in odds_str.upper() or not odds_str

                odds = {}
                if not scratched:
                    win_odds = parse_odds_to_decimal(odds_str)
                    if win_odds and win_odds < 999:
                        odds = {
                            self.source_name: OddsData(
                                win=win_odds, source=self.source_name, last_updated=datetime.now()
                            )
                        }

                runners.append(Runner(number=number, name=name, odds=odds, scratched=scratched))
            except (ValueError, AttributeError):
                self.logger.warning("Could not parse RacingPost runner, skipping.", parser=parser)
                continue
        return runners

    def _get_headers(self) -> dict:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/107.0.0.0 Safari/537.36"
            )
        }
