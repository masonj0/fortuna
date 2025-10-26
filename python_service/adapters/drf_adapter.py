# python_service/adapters/drf_adapter.py
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


class DRFAdapter(BaseAdapter):
    """
    Adapter for drf.com.
    This adapter now follows the modern fetch/parse pattern.
    """

    def __init__(self, config):
        super().__init__(source_name="DRF", base_url="https://www.drf.com", config=config)

    async def _fetch_data(self, http_client: httpx.AsyncClient, date: str) -> Any:
        """Fetches the raw HTML from the DRF entries page."""
        url = f"/entries/{date}/USA"
        response = await self.make_request(http_client, "GET", url)
        return {"html": response.text, "date": date} if response else None

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses the raw HTML into a list of Race objects."""
        if not raw_data or not raw_data.get("html"):
            return []

        html = raw_data["html"]
        race_date = raw_data["date"]
        soup = BeautifulSoup(html, "html.parser")

        venue_text = soup.select_one("div.track-info h1").text
        venue = normalize_venue_name(venue_text.split(" - ")[0].replace("Entries for ", ""))

        races = []
        for race_entry in soup.select("div.race-entries"):
            race_number = int(race_entry["data-race-number"])
            post_time_str = race_entry.select_one(".post-time").text.replace("Post Time: ", "").strip()
            start_time = parse(f"{race_date} {post_time_str}")

            runners = []
            for entry in race_entry.select("li.entry"):
                if "scratched" in entry.get("class", []):
                    continue

                number = int(entry.select_one(".program-number").text)
                name = entry.select_one(".horse-name").text
                odds_str = entry.select_one(".odds").text.replace('-', '/')

                win_odds = parse_odds_to_decimal(odds_str)
                odds = {}
                if win_odds:
                    odds[self.source_name] = OddsData(win=win_odds, source=self.source_name, last_updated=datetime.now())

                runners.append(Runner(number=number, name=name, odds=odds))

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

        return races
