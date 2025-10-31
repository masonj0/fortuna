# python_service/adapters/drf_adapter.py
from datetime import datetime
from typing import Any, List, Optional
from bs4 import BeautifulSoup, Tag
from dateutil.parser import parse

from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import normalize_venue_name
from .base_v3 import BaseAdapterV3


class DRFAdapter(BaseAdapterV3):
    """
    Adapter for drf.com, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "DRF"
    BASE_URL = "https://www.drf.com"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config
        )

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """Fetches the raw HTML from the DRF entries page."""
        url = f"/entries/{date}/USA"
        response = await self.make_request(self.http_client, "GET", url)
        return {"html": response.text, "date": date} if response and response.text else None

    def _parse_races(self, raw_data: Optional[dict]) -> List[Race]:
        """Parses the raw HTML into a list of Race objects."""
        if not raw_data or not raw_data.get("html"):
            return []

        html = raw_data["html"]
        race_date = raw_data["date"]
        soup = BeautifulSoup(html, "html.parser")

        venue_node = soup.select_one("div.track-info h1")
        if not venue_node:
            self.logger.warning("Could not find venue name on DRF page.")
            return []

        venue_text = venue_node.text
        venue = normalize_venue_name(
            venue_text.split(" - ")[0].replace("Entries for ", "")
        )

        races = []
        for race_entry in soup.select("div.race-entries"):
            try:
                race_number_str = race_entry.get("data-race-number")
                if not race_number_str or not race_number_str.isdigit():
                    continue
                race_number = int(race_number_str)

                post_time_node = race_entry.select_one(".post-time")
                if not post_time_node:
                    continue
                post_time_str = post_time_node.text.replace("Post Time: ", "").strip()
                start_time = parse(f"{race_date} {post_time_str}")

                runners = []
                for entry in race_entry.select("li.entry"):
                    if "scratched" in entry.get("class", []):
                        continue

                    number_node = entry.select_one(".program-number")
                    if not number_node or not number_node.text.isdigit():
                        continue
                    number = int(number_node.text)

                    name_node = entry.select_one(".horse-name")
                    if not name_node:
                        continue
                    name = name_node.text

                    odds_node = entry.select_one(".odds")
                    odds_str = odds_node.text.replace("-", "/") if odds_node else ""

                    win_odds = parse_odds_to_decimal(odds_str)
                    odds = {}
                    if win_odds:
                        odds[self.source_name] = OddsData(
                            win=win_odds,
                            source=self.source_name,
                            last_updated=datetime.now(),
                        )

                    runners.append(Runner(number=number, name=name, odds=odds))

                if not runners:
                    continue

                race = Race(
                    id=f"drf_{venue.replace(' ', '').lower()}_{race_date}_{race_number}",
                    venue=venue,
                    race_number=race_number,
                    start_time=start_time,
                    runners=runners,
                    source=self.source_name,
                    field_size=len(runners),
                )
                races.append(race)
            except (ValueError, KeyError, TypeError):
                self.logger.warning(
                    "Failed to parse a race on DRF, skipping.", exc_info=True
                )
                continue
        return races
