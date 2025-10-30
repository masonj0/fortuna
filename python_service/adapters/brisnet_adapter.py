# python_service/adapters/brisnet_adapter.py
from datetime import datetime
from typing import Any, List
from bs4 import BeautifulSoup
from dateutil.parser import parse

from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import normalize_venue_name
from .base_v3 import BaseAdapterV3


class BrisnetAdapter(BaseAdapterV3):
    """
    Adapter for brisnet.com, migrated to BaseAdapterV3.
    """

    SOURCE_NAME = "Brisnet"
    BASE_URL = "https://www.brisnet.com"

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config
        )

    async def _fetch_data(self, date: str) -> Any:
        """Fetches the raw HTML from the Brisnet race page."""
        # Note: Brisnet URL structure seems to require a track code, e.g., 'CD' for Churchill Downs.
        # This implementation will need to be improved to dynamically handle different tracks.
        # For now, it is hardcoded to Churchill Downs as a placeholder.
        url = f"/race/{date}/CD"
        response = await self.make_request(self.http_client, "GET", url)
        return {"html": response.text, "date": date} if response else None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses the raw HTML into a list of Race objects."""
        if not raw_data or not raw_data.get("html"):
            return []

        html = raw_data["html"]
        race_date = raw_data["date"]
        soup = BeautifulSoup(html, "html.parser")

        venue_text_node = soup.select_one("header h1")
        if not venue_text_node:
            self.logger.warning("Could not find venue name on Brisnet page.")
            return []

        venue_text = venue_text_node.text
        venue = normalize_venue_name(venue_text.split(" - ")[0])

        races = []
        for race_section in soup.select("section.race"):
            try:
                race_number = int(race_section["data-racenumber"])
                post_time_str = (
                    race_section.select_one(".race-title span")
                    .text.replace("Post Time: ", "")
                    .strip()
                )
                start_time = parse(f"{race_date} {post_time_str}")

                runners = []
                for row in race_section.select("tbody tr"):
                    if "scratched" in row.get("class", []):
                        continue

                    cells = row.find_all("td")
                    number = int(cells[0].text)
                    name = cells[1].text.strip()
                    odds_str = cells[2].text.strip()

                    win_odds = parse_odds_to_decimal(odds_str)
                    odds = {}
                    if win_odds:
                        odds[self.source_name] = OddsData(
                            win=win_odds,
                            source=self.source_name,
                            last_updated=datetime.now(),
                        )

                    runners.append(Runner(number=number, name=name, odds=odds))

                race = Race(
                    id=f"brisnet_{venue.replace(' ', '').lower()}_{race_date}_{race_number}",
                    venue=venue,
                    race_number=race_number,
                    start_time=start_time,
                    runners=runners,
                    source=self.source_name,
                    field_size=len(runners),
                )
                races.append(race)
            except (AttributeError, ValueError, IndexError):
                self.logger.warning(
                    "Failed to parse a race on Brisnet, skipping.", exc_info=True
                )
                continue

        return races
