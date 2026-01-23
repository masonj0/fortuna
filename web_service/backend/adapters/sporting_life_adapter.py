# python_service/adapters/sporting_life_adapter.py

import asyncio
from datetime import datetime
from typing import Any
from typing import List
from typing import Optional

from bs4 import BeautifulSoup
from bs4 import Tag

from ..models import OddsData
from ..models import Race
from ..models import Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import clean_text
from .base_adapter_v3 import BaseAdapterV3


class SportingLifeAdapter(BaseAdapterV3):
    """
    Adapter for sportinglife.com, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "SportingLife"
    BASE_URL = "https://www.sportinglife.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """
        Fetches the raw HTML for all race pages for a given date.
        Returns a dictionary containing the HTML content and the date.
        """
        index_url = f"/racing/racecards/{date}"
        index_response = await self.make_request(
            self.http_client, "GET", index_url, headers=self._get_headers()
        )
        if not index_response:
            self.logger.warning("Failed to fetch SportingLife index page", url=index_url)
            return None

        index_soup = BeautifulSoup(index_response.text, "html.parser")
        links = {
            a["href"]
            for a in index_soup.select("a.hr-race-card-race-link")
            if "racecard" in a.get("href", "") and any(char.isdigit() for char in a["href"])
        }

        async def fetch_single_html(url_path: str):
            response = await self.make_request(
                self.http_client, "GET", url_path, headers=self._get_headers()
            )
            return response.text if response else ""

        tasks = [fetch_single_html(link) for link in links]
        html_pages = await asyncio.gather(*tasks)
        return {"pages": html_pages, "date": date}

    def _get_headers(self) -> dict:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Host": "www.sportinglife.com",
            "Pragma": "no-cache",
            "sec-ch-ua": '"Not/A)Brand";v="99", "Google Chrome";v="115", "Chromium";v="115"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Referer": "https://www.sportinglife.com/racing/racecards",
        }

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
                soup = BeautifulSoup(html, "html.parser")

                header_text = clean_text(soup.select_one("h1.hr-race-header-title__text").get_text())
                parts = header_text.split()
                race_time_str = parts[0]
                track_name = " ".join(parts[1:])

                start_time = datetime.combine(race_date, datetime.strptime(race_time_str, "%H:%M").time())

                race_number = 1
                nav_links = soup.select("a.hr-race-header-navigation-link")
                active_link = soup.select_one("a.hr-race-header-navigation-link--active")
                if active_link and nav_links:
                    try:
                        # Add 1 because list index is 0-based
                        race_number = nav_links.index(active_link) + 1
                    except ValueError:
                        self.logger.warning("Active race link not found in navigation links.")

                runners = [self._parse_runner(row) for row in soup.select("div.hr-racing-runner-card-wrapper")]

                race = Race(
                    id=f"sl_{track_name.replace(' ', '')}_{start_time.strftime('%Y%m%d')}_R{race_number}",
                    venue=track_name,
                    race_number=race_number,
                    start_time=start_time,
                    runners=[r for r in runners if r],
                    source=self.source_name,
                )
                all_races.append(race)
            except (AttributeError, ValueError):
                self.logger.warning(
                    "Error parsing a race from SportingLife, skipping race.",
                    exc_info=True,
                )
                continue
        return all_races

    def _parse_runner(self, row: Tag) -> Optional[Runner]:
        try:
            name_node = row.select_one("a[href*='/racing/profiles/horse/']")
            if not name_node:
                return None
            # Extract the name, removing any non-alphanumeric trailing characters
            name = clean_text(name_node.get_text()).splitlines()[0].strip()

            num_node = row.select_one("span.hr-racing-runner-saddle-cloth-number")
            if not num_node:
                return None
            num_str = clean_text(num_node.get_text())
            number = int("".join(filter(str.isdigit, num_str)))

            odds_node = row.select_one("span.hr-racing-runner-betting-odds__odd")
            odds_str = clean_text(odds_node.get_text()) if odds_node else ""

            win_odds = parse_odds_to_decimal(odds_str)
            odds_data = (
                {
                    self.source_name: OddsData(
                        win=win_odds,
                        source=self.source_name,
                        last_updated=datetime.now(),
                    )
                }
                if win_odds and win_odds < 999
                else {}
            )
            return Runner(number=number, name=name, odds=odds_data)
        except (AttributeError, ValueError):
            self.logger.warning("Failed to parse a runner on SportingLife, skipping runner.")
            return None
