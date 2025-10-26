# python_service/adapters/brisnet_adapter.py
from datetime import datetime
from typing import Any, Dict, List
import httpx
import structlog
from bs4 import BeautifulSoup
from dateutil.parser import parse

from ..models import OddsData, Race, Runner
from ..utils.odds import parse_odds_to_decimal
from ..utils.text import normalize_venue_name
from .base import BaseAdapter

log = structlog.get_logger(__name__)


class BrisnetAdapter(BaseAdapter):
    """
    Adapter for brisnet.com.
    This adapter now follows the modern fetch/parse pattern.
    """

    def __init__(self, config):
        super().__init__(source_name="Brisnet", base_url="https://www.brisnet.com", config=config)

    async def _fetch_data(self, http_client: httpx.AsyncClient, date: str) -> Any:
        """Fetches the raw HTML from the Brisnet race page."""
        url = f"/race/{date}/CD"
        response = await self.make_request(http_client, "GET", url)
        return {"html": response.text, "date": date} if response else None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses the raw HTML into a list of Race objects."""
        if not raw_data or not raw_data.get("html"):
            return []

        html = raw_data["html"]
        race_date = raw_data["date"]
        soup = BeautifulSoup(html, "html.parser")

        venue_text = soup.select_one("header h1").text
        venue = normalize_venue_name(venue_text.split(" - ")[0])

        races = []
        for race_section in soup.select("section.race"):
            race_number = int(race_section["data-racenumber"])
            post_time_str = race_section.select_one(".race-title span").text.replace("Post Time: ", "").strip()
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
                    odds[self.source_name] = OddsData(win=win_odds, source=self.source_name, last_updated=datetime.now())

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

        return races
