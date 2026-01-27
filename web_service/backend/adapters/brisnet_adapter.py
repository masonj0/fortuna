# python_service/adapters/brisnet_adapter.py
from datetime import datetime
from typing import List
from typing import Optional

from selectolax.parser import HTMLParser
from dateutil.parser import parse

from python_service.core.smart_fetcher import BrowserEngine, FetchStrategy, StealthMode
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

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(
            primary_engine=BrowserEngine.PLAYWRIGHT,
            enable_js=True,
            stealth_mode=StealthMode.CAMOUFLAGE,
            block_resources=True,
            max_retries=3,
            timeout=30,
        )

    async def _fetch_track_list(self) -> List[str]:
        """Fetches the list of active tracks from the Brisnet index page."""
        url = "/cgi-bin/intoday.cgi"
        response = await self.make_request("GET", url, headers=self._get_headers())
        if not response or not response.text:
            return []

        parser = HTMLParser(response.text)
        # Find links that look like track entries
        links = [
            a.attributes.get("href")
            for a in parser.css("a[href*='briswatch.cgi']")
            if a.attributes.get("href")
        ]
        return list(set(links))

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """Fetches the raw HTML from the Brisnet race page."""
        url = "/cgi-bin/intoday.cgi"
        response = await self.make_request("GET", url, headers=self._get_headers())
        if not response or not response.text:
            return None

        # Save the raw HTML for debugging in CI
        try:
            with open("brisnet_debug.html", "w", encoding="utf-8") as f:
                f.write(response.text)
        except Exception as e:
            self.logger.warning("Failed to save debug HTML for Brisnet", error=str(e))

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
        parser = HTMLParser(html)

        races = []
        # Update selector to use CSS via selectolax
        for race_link in parser.css("a[href*='brisnet.com/cgi-bin/briswatch.cgi/public/Brad/TODAY.PM']"):
            try:
                race_number_str = race_link.text().strip()
                if not race_number_str.isdigit():
                    continue
                race_number = int(race_number_str)

                venue = "Unknown"
                # Selectolax doesn't have find_parent quite the same way, but we can navigate up
                # Simplified for now as per original logic
                parent = race_link.parent
                while parent and parent.tag != "table":
                    parent = parent.parent

                if parent:
                    caption = parent.css_first("caption")
                    if caption:
                        venue = normalize_venue_name(caption.text().strip())

                start_time = datetime.now()

                race = Race(
                    id=f"brisnet_{venue.replace(' ', '').lower()}_{race_date}_{race_number}",
                    venue=venue,
                    race_number=race_number,
                    start_time=start_time,
                    runners=[],
                    source=self.SOURCE_NAME,
                )
                races.append(race)
            except (ValueError, IndexError, TypeError) as e:
                self.logger.warning(
                    "Failed to parse a race link on Brisnet",
                    link=race_link.attributes.get("href"),
                    error=e,
                )
                continue

        return races
