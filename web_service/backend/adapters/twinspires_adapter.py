# python_service/adapters/twinspires_adapter.py
from datetime import datetime
from typing import Any
from typing import List

from bs4 import BeautifulSoup

from ..models import OddsData
from ..models import Race
from ..models import Runner
from ..utils.odds import parse_odds_to_decimal
from .base_adapter_v3 import BaseAdapterV3


class TwinSpiresAdapter(BaseAdapterV3):
    """
    Adapter for twinspires.com.
    This is a placeholder for a full implementation using the discovered JSON API.
    """

    SOURCE_NAME = "TwinSpires"
    BASE_URL = "https://www.twinspires.com"

    def __init__(self, config=None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    async def _fetch_data(self, date: str) -> Any:
        """
        [MODIFIED FOR OFFLINE DEVELOPMENT]
        Reads HTML content from a local fixture file instead of making a live API call.
        This is a temporary measure to allow development while the live API is blocking requests.
        """
        # Read the local HTML fixture
        try:
            with open("tests/fixtures/twinspires_sample.html", "r") as f:
                html_content = f.read()
        except FileNotFoundError:
            self.logger.error("TwinSpires test fixture not found.")
            return None

        # To maintain the data structure the parser expects, we will create a mock
        # raw_data object that resembles the original API response, but includes
        # the HTML content.
        return {
            "html_content": html_content,
            "mock_track_data": {"trackId": "cd", "trackName": "Churchill Downs", "raceType": "Thoroughbred"},
            "mock_race_card": {"raceNumber": 5, "postTime": "2025-10-26T16:30:00Z"},
        }

    def _parse_races(self, raw_data: Any) -> List[Dict[str, Any]]:
        """
        [MODIFIED FOR OFFLINE DEVELOPMENT]
        Parses race and runner data from the mock raw_data object, which now
        includes the HTML content from the local fixture. Returns a list of dictionaries.
        """
        if not raw_data or "html_content" not in raw_data:
            return []

        self.logger.info("Parsing TwinSpires data from local fixture.")

        html_content = raw_data["html_content"]
        track = raw_data["mock_track_data"]
        race_card = raw_data["mock_race_card"]

        # Parse the runners from the HTML content
        runners = self._parse_runners_from_html(html_content)

        try:
            start_time = datetime.fromisoformat(race_card.get("postTime").replace("Z", "+00:00"))

            race_dict = {
                "id": f"ts_{track.get('trackId')}_{race_card.get('raceNumber')}",
                "venue": track.get("trackName"),
                "race_number": race_card.get("raceNumber"),
                "start_time": start_time,
                "discipline": track.get("raceType", "Unknown"),
                "runners": [runner.model_dump() for runner in runners],
                "source": self.SOURCE_NAME,
            }
            return [race_dict]
        except Exception as e:
            self.logger.warning(
                "Failed to parse race card from mock data.",
                error=e,
                exc_info=True,
            )
            return []

    def _parse_runners_from_html(self, html_content: str) -> List[Runner]:
        """Parses runner data from a race card's HTML content."""
        runners = []
        soup = BeautifulSoup(html_content, "html.parser")
        runner_elements = soup.select("li.runner")

        for element in runner_elements:
            try:
                scratched = "scratched" in element.get("class", [])

                number_tag = element.select_one("span.runner-number")
                name_tag = element.select_one("span.runner-name")
                odds_tag = element.select_one("span.runner-odds")

                if not all([number_tag, name_tag, odds_tag]):
                    continue

                number = int(number_tag.text.strip())
                name = name_tag.text.strip()
                odds_str = odds_tag.text.strip()

                odds = {}
                if not scratched and odds_str not in ["SCR", ""]:
                    win_odds = parse_odds_to_decimal(odds_str)
                    if win_odds:
                        odds[self.SOURCE_NAME] = OddsData(
                            win=win_odds,
                            source=self.SOURCE_NAME,
                            last_updated=datetime.now(),
                        )

                runners.append(
                    Runner(
                        number=number,
                        name=name,
                        scratched=scratched,
                        odds=odds,
                    )
                )
            except (ValueError, TypeError) as e:
                self.logger.warning("Failed to parse a runner, skipping.", error=e, exc_info=True)
                continue

        return runners

    async def get_races(self, date: str) -> List[Dict[str, Any]]:
        """
        Orchestrates the fetching and parsing of race data for a given date.
        This method will be called by the FortunaEngine.
        """
        self.logger.info(f"Getting races for {date} from {self.SOURCE_NAME}")
        raw_data = await self._fetch_data(date)
        if raw_data:
            return self._parse_races(raw_data)
        return []
