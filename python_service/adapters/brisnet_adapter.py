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
    """Adapter for brisnet.com."""

    def __init__(self, config):
        super().__init__(source_name="Brisnet", base_url="https://www.brisnet.com", config=config)

    async def fetch_races(self, date: str, http_client: httpx.AsyncClient) -> Dict[str, Any]:
        start_time = datetime.now()
        url = f"{self.base_url}/race/{date}/CD"

        try:
            response = await self.make_request(http_client, "GET", url)
            if not response or response.status_code != 200:
                return self._format_response([], start_time, error_message="Failed to fetch data from Brisnet")

            races = self._parse_races(response.text, date)
            return self._format_response(races, start_time)
        except Exception as e:
            log.error("Error fetching races from Brisnet", error=str(e), exc_info=True)
            return self._format_response([], start_time, error_message=str(e))

    def _parse_races(self, raw_data: str, race_date: str) -> List[Race]:
        soup = BeautifulSoup(raw_data, "html.parser")

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

    def _format_response(self, races: List[Race], start_time: datetime, **kwargs) -> Dict[str, Any]:
        return {
            "races": [race.model_dump() for race in races],
            "source_info": {
                "name": self.source_name,
                "status": "SUCCESS" if not kwargs.get("error_message") else "FAILED",
                "races_fetched": len(races),
                "error_message": kwargs.get("error_message"),
                "fetch_duration": (datetime.now() - start_time).total_seconds(),
            },
        }
