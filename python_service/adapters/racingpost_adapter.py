# python_service/adapters/racingpost_adapter.py
import asyncio
from datetime import datetime
from typing import List
from typing import Optional

from selectolax.parser import HTMLParser

from ..core.exceptions import AdapterParsingError
from ..models import OddsData
from ..models import Race
from ..models import Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text
from ..utils.text import normalize_venue_name
from .base import BaseAdapter


class RacingPostAdapter(BaseAdapter):
    """A production-ready adapter for scraping Racing Post racecards."""

    def __init__(self, config=None):
        super().__init__(source_name="RacingPost", base_url="https://www.racingpost.com", config=config)

    async def fetch_races(self, date: str, http_client) -> List[Race]:
        """
        Fetches all UK & Ireland races for a given date from racingpost.com.
        """
        race_card_urls = await self._get_race_card_urls(date, http_client)

        tasks = [self._fetch_and_parse_race(url, date, http_client) for url in race_card_urls]
        return [race for race in await asyncio.gather(*tasks) if race]

    async def _get_race_card_urls(self, date: str, http_client) -> list[str]:
        """Gets all individual race card URLs for a given date."""
        url = f"/racecards/{date}"
        response = await self.make_request(http_client, "GET", url, headers=self._get_headers())
        parser = HTMLParser(response.text)
        links = parser.css('a[data-test-selector^="RC-meetingItem__link_race"]')
        return [f"{self.base_url}{link.attributes['href']}" for link in links]

    async def _fetch_and_parse_race(self, url: str, date: str, http_client) -> Optional[Race]:
        try:
            response = await self.make_request(
                http_client, "GET", url.replace(self.base_url, ""), headers=self._get_headers()
            )
            parser = HTMLParser(response.text)

            venue_raw = parser.css_first('a[data-test-selector="RC-course__name"]').text(strip=True)
            venue = normalize_venue_name(venue_raw)

            race_time_str = parser.css_first('span[data-test-selector="RC-course__time"]').text(strip=True)
            race_datetime_str = f"{date} {race_time_str}"
            start_time = datetime.strptime(race_datetime_str, "%Y-%m-%d %H:%M")

            runners = self._parse_runners(parser)

            if venue and runners:
                race_number = self._get_race_number(parser, start_time)
                return Race(
                    id=f"rp_{venue.lower().replace(' ', '')}_{date}_{race_number}",
                    venue=venue,
                    race_number=race_number,
                    start_time=start_time,
                    runners=runners,
                    source=self.source_name,
                )
            return None
        except (AttributeError, ValueError) as e:
            raise AdapterParsingError(self.source_name, f"Failed to parse race at {url}") from e

    def _get_race_number(self, parser: HTMLParser, start_time: datetime) -> int:
        """Derives the race number by finding the active time in the nav bar."""
        time_str_to_find = start_time.strftime("%H:%M")
        time_links = parser.css('a[data-test-selector="RC-raceTime"]')
        for i, link in enumerate(time_links):
            if link.text(strip=True) == time_str_to_find:
                return i + 1
        return 1  # Fallback

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
                self.logger.warning("Could not parse runner, skipping.", parser=parser)
                continue
        return runners

    def _get_headers(self) -> dict:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/107.0.0.0 Safari/537.36"
            )
        }
