# tests/utils.py
from datetime import datetime
from decimal import Decimal
from typing import Dict
from typing import List

from python_service.models import OddsData
from python_service.models import Race
from python_service.models import Runner


def create_mock_race(
    source: str,
    track_name: str,
    race_number: int,
    start_time: datetime,
    runners_data: List[Dict],
) -> dict:
    """
    Creates a dictionary representing a race, suitable for Pydantic model validation.
    This is a test utility to generate consistent race data.
    """
    runners = []
    for i, runner_info in enumerate(runners_data):
        odds_data = {}
        if "odds" in runner_info:
            odds_value = Decimal(str(runner_info["odds"]))
            odds_data[source] = OddsData(win=odds_value, source=source, last_updated=datetime.now())

        runners.append(
            Runner(
                number=runner_info.get("number", i + 1),
                name=runner_info.get("name", f"Runner {i + 1}"),
                odds=odds_data,
                scratched=runner_info.get("scratched", False),
            ).model_dump()
        )

    # Use Pydantic model to create and then dump the data to ensure it's valid
    race = Race(
        id=f"test_{track_name}_{race_number}",
        venue=track_name,
        race_number=race_number,
        start_time=start_time,
        runners=runners,
        source=source,
    )
    return race.model_dump()
