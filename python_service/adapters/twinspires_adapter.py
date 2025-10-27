# python_service/adapters/twinspires_adapter.py
from datetime import datetime
from typing import Any, List

from bs4 import BeautifulSoup
from dateutil.parser import parse

from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal
from .base_v3 import BaseAdapterV3


class TwinSpiresAdapter(BaseAdapterV3):
    """
    Adapter for twinspires.com, migrated to BaseAdapterV3.
    """
    SOURCE_NAME = "TwinSpires"
    BASE_URL = "https://www.twinspires.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Any:
        """Fetches the raw HTML from the TwinSpires race page."""
        # Note: This adapter's URL structure might be more complex and require discovery.
        # This is a simplified placeholder based on the original implementation.
        url = f"/races/{date}"
        response = await self.make_request(self.http_client, "GET", url)
        return {"html": response.text, "date": date} if response else None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses the raw HTML into a list of Race objects."""
        if not raw_data or not raw_data.get("html"):
            return []

        html = raw_data["html"]
        race_date = raw_data["date"]
        soup = BeautifulSoup(html, "html.parser")

        all_races = []
        # Assuming a page can have multiple race cards
        for race_card in soup.select("#race-card"):
            try:
                race_title_parts = race_card.select_one("h1").text.split(" - ")
                race_number = int(race_title_parts[0].split(" ")[1])
                venue = race_title_parts[1]

                # Use the date from fetch, not from parsed title
                start_time = self._parse_start_time(race_card, race_date)

                runners = []
                for runner_item in race_card.select(".runners-list .runner"):
                    if "scratched" in runner_item.get("class", []):
                        continue

                    number = int(runner_item.select_one(".runner-number").text)
                    name = runner_item.select_one(".runner-name").text
                    odds_str = runner_item.select_one(".runner-odds").text

                    odds_decimal = parse_odds_to_decimal(odds_str)
                    odds = {}
                    if odds_decimal:
                        odds[self.source_name] = OddsData(win=odds_decimal, source=self.source_name, last_updated=datetime.now())

                    runners.append(Runner(number=number, name=name, odds=odds, scratched=False))

                race = Race(
                    id=f"ts_{venue.replace(' ', '').lower()}_{race_date}_{race_number}",
                    venue=venue,
                    race_number=race_number,
                    start_time=start_time,
                    runners=runners,
                    source=self.source_name,
                )
                all_races.append(race)
            except (AttributeError, ValueError, IndexError):
                self.logger.warning("Failed to parse a race on TwinSpires, skipping.", exc_info=True)
                continue
        return all_races

    def _parse_start_time(self, soup: "BeautifulSoup", race_date: str) -> datetime:
        post_time_str = soup.select_one(".post-time").text.replace("Post Time: ", "").strip()
        full_datetime_str = f"{race_date} {post_time_str}"
        return parse(full_datetime_str)
