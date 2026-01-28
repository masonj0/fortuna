# python_service/adapters/brisnet_adapter.py
import asyncio
from datetime import datetime
from typing import List
from typing import Optional

from selectolax.parser import HTMLParser
from dateutil.parser import parse as parse_time

from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy
from ..models import Race
from ..models import Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3
from .mixins import BrowserHeadersMixin, DebugMixin
from .utils.odds_validator import create_odds_data


class BrisnetAdapter(BrowserHeadersMixin, DebugMixin, BaseAdapterV3):
    """
    Adapter for brisnet.com, migrated to BaseAdapterV3 with enhanced track detection.
    """

    SOURCE_NAME = "Brisnet"
    BASE_URL = "https://www.brisnet.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(
            primary_engine=BrowserEngine.PLAYWRIGHT,
            enable_js=True,
            timeout=30,
        )

    def _get_headers(self) -> dict:
        return self._get_browser_headers(host="www.brisnet.com")

    async def _fetch_track_links(self) -> List[str]:
        """Fetches the list of active track links from the Brisnet index page."""
        url = "/cgi-bin/intoday.cgi"
        response = await self.make_request("GET", url, headers=self._get_headers())
        if not response or not response.text:
            return []

        parser = HTMLParser(response.text)
        # Find links that look like track entries (briswatch.cgi links)
        links = []
        for a in parser.css("a[href*='briswatch.cgi']"):
            href = a.attributes.get("href")
            if href:
                # Ensure it's an absolute URL or relative to base
                if not href.startswith("http"):
                    href = href if href.startswith("/") else f"/{href}"
                links.append(href)

        return list(set(links))

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """Fetches the raw HTML for all active tracks for the given date."""
        track_links = await self._fetch_track_links()
        if not track_links:
            self.logger.warning("No active tracks found on Brisnet index page.")
            return None

        semaphore = asyncio.Semaphore(5)

        async def fetch_track_page(url: str):
            async with semaphore:
                try:
                    response = await self.make_request("GET", url, headers=self._get_headers())
                    if response:
                        self._save_debug_html(response.text, f"brisnet_{url.split('/')[-1]}_{date}")
                    return response.text if response else ""
                except Exception as e:
                    self.logger.warning("Failed to fetch track page", url=url, error=str(e))
                    return ""

        tasks = [fetch_track_page(link) for link in track_links]
        pages = await asyncio.gather(*tasks)

        return {
            "pages": [p for p in pages if p],
            "date": date
        }

    def _parse_races(self, raw_data: Optional[dict]) -> List[Race]:
        """Parses the raw HTML pages into a list of Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        race_date = raw_data["date"]
        all_races = []

        for html in raw_data["pages"]:
            parser = HTMLParser(html)

            venue_node = parser.css_first("header h1")
            venue = "Unknown"
            if venue_node:
                venue_text = venue_node.text().split(" - ")[0]
                venue = normalize_venue_name(venue_text)

            for race_section in parser.css("section.race"):
                try:
                    race_number_str = race_section.attributes.get("data-racenumber")
                    if not race_number_str or not race_number_str.isdigit():
                        continue
                    race_number = int(race_number_str)

                    post_time_node = race_section.css_first(".race-title span")
                    if not post_time_node:
                        continue
                    post_time_str = post_time_node.text().replace("Post Time: ", "").strip()

                    try:
                        start_time = parse_time(f"{race_date} {post_time_str}")
                    except (ValueError, TypeError):
                        start_time = datetime.now()

                    runners = []
                    for row in race_section.css("tbody tr"):
                        classes = row.attributes.get("class", "")
                        if classes and "scratched" in classes.lower():
                            continue

                        cells = row.css("td")
                        if len(cells) < 3:
                            continue

                        number_text = cells[0].text().strip()
                        number_digits = "".join(filter(str.isdigit, number_text))
                        number = int(number_digits) if number_digits else 0

                        name = cells[1].text().strip()
                        odds_str = cells[2].text().strip()

                        win_odds = parse_odds_to_decimal(odds_str)
                        odds = {}
                        if odds_data := create_odds_data(self.source_name, win_odds):
                            odds[self.source_name] = odds_data

                        runners.append(Runner(number=number, name=name, odds=odds))

                    if not runners:
                        continue

                    race = Race(
                        id=f"brisnet_{venue.replace(' ', '').lower()}_{race_date}_{race_number}",
                        venue=venue,
                        race_number=race_number,
                        start_time=start_time,
                        runners=runners,
                        source=self.source_name,
                        field_size=len(runners),
                    )
                    all_races.append(race)
                except Exception:
                    self.logger.warning("Failed to parse a race on Brisnet, skipping.", exc_info=True)
                    continue

        return all_races
