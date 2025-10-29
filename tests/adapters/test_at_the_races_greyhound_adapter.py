# tests/adapters/test_at_the_races_greyhound_adapter.py

from datetime import datetime
import pytest
from python_service.adapters.at_the_races_greyhound_adapter import AtTheRacesGreyhoundAdapter
from python_service.models import Race, Runner


@pytest.fixture
def adapter():
    return AtTheRacesGreyhoundAdapter()


def load_fixture(name):
    with open(f"tests/fixtures/{name}", "r") as f:
        return f.read()


def test_parse_races_with_valid_html(adapter):
    html = load_fixture("at_the_races_greyhounds.html")
    raw_data = {"pages": [html], "date": "2025-10-29"}

    races = adapter._parse_races(raw_data)

    assert len(races) == 1
    race = races[0]
    assert isinstance(race, Race)
    assert race.venue == "Monmore"
    assert race.start_time.strftime("%Y-%m-%d %H:%M") == "2025-10-29 18:17"
    assert race.race_number == 1
    assert len(race.runners) == 2

    runner1 = race.runners[0]
    assert isinstance(runner1, Runner)
    assert runner1.number == 1
    assert runner1.name == "Crossfield Larry"
    assert runner1.odds["AtTheRacesGreyhound"].win == 3.5

    runner2 = race.runners[1]
    assert isinstance(runner2, Runner)
    assert runner2.number == 2
    assert runner2.name == "Stouke A Star"
    assert runner2.odds["AtTheRacesGreyhound"].win == 3.75
