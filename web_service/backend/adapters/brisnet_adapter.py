# python_service/adapters/brisnet_adapter.py
from datetime import datetime
from typing import List
from typing import Optional

from bs4 import BeautifulSoup
from dateutil.parser import parse

from ..models import OddsData
from ..models import Race
from ..models import Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3


class BrisnetAdapter(BaseAdapterV3):
    """
    Adapter for brisnet.com, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "Brisnet"
    BASE_URL = "https://www.brisnet.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """Fetches the raw HTML from the Brisnet race page."""
        url = "/cgi-bin/intoday.cgi"
        response = await self.make_request(self.http_client, "GET", url, headers=self._get_headers())
        if not response or not response.text:
            return None

        # Save the raw HTML for debugging in CI
        with open("brisnet_debug.html", "w", encoding="utf-8") as f:
            f.write(response.text)

        return {"html": response.text, "date": date}

    def _get_headers(self) -> dict:
        return {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Host": "www.brisnet.com",
            "Pragma": "no-cache",
            "sec-ch-ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        }

    def _parse_races(self, raw_data: Optional[dict]) -> List[Race]:
        """Parses the raw HTML into a list of Race objects."""
        if not raw_data or not raw_data.get("html"):
            self.logger.warning("No HTML content received from Brisnet")
            return []

        html = raw_data["html"]
        race_date = raw_data["date"]
        soup = BeautifulSoup(html, "html.parser")

        races = []
        for race_link in soup.select("a[href*='brisnet.com/cgi-bin/briswatch.cgi/public/Brad/TODAY.PM']"):
            try:
                race_number_str = race_link.text.strip()
                if not race_number_str.isdigit():
                    continue
                race_number = int(race_number_str)

                # Venue and start time are not available on the index page, so we have to be creative
                # This is a significant simplification and may need to be revisited
                venue = "Unknown"
                if parent_table := race_link.find_parent("table"):
                    if caption := parent_table.find("caption"):
                        venue = normalize_venue_name(caption.text.strip())

                # Create a placeholder start time as it's not available on this page
                start_time = datetime.now()

                # Since we don't have runner data on this page, we create a placeholder race
                # A more complete implementation would require fetching each race link
                race = Race(
                    id=f"brisnet_{venue.replace(' ', '').lower()}_{race_date}_{race_number}",
                    venue=venue,
                    race_number=race_number,
                    start_time=start_time,
                    runners=[],
                    source=self.source_name,
                )
                races.append(race)
            except (ValueError, IndexError, TypeError) as e:
                self.logger.warning(
                    "Failed to parse a race link on Brisnet",
                    link=race_link.get("href"),
                    error=e,
                    exc_info=True,
                )
                continue

        return races
