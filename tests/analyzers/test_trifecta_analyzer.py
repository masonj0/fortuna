# Dedicated test suite for the TrifectaAnalyzer, resurrected and expanded.
import pytest
from datetime import datetime
from python_service.analyzer import TrifectaAnalyzer
from python_service.models import Race, Runner

@pytest.fixture
def analyzer():
    return TrifectaAnalyzer()

@pytest.fixture
def runners():
    return []

@pytest.fixture
def create_race(runners):
    return Race(
        id='test-race',
        venue='TEST',
        race_number=1,
        start_time=datetime.now(),
        runners=runners,
        source='test'
    )

def test_analyzer_name(analyzer):
    assert analyzer.name == "trifecta_analyzer"

# Test cases resurrected from legacy scorer and logic tests
def test_qualifies_with_exactly_three_runners(analyzer, create_race):
    from decimal import Decimal
    from python_service.models import OddsData
    odds1 = {"TestOdds": OddsData(win=Decimal("3.0"), source="TestOdds", last_updated=datetime.now())}
    odds2 = {"TestOdds": OddsData(win=Decimal("4.0"), source="TestOdds", last_updated=datetime.now())}
    odds3 = {"TestOdds": OddsData(win=Decimal("5.0"), source="TestOdds", last_updated=datetime.now())}
    create_race.runners = [
        Runner(number=1, name='A', odds=odds1, scratched=False),
        Runner(number=2, name='B', odds=odds2, scratched=False),
        Runner(number=3, name='C', odds=odds3, scratched=False)
    ]
    assert analyzer.is_race_qualified(create_race) is True

def test_qualifies_with_more_than_three_runners(analyzer, create_race):
    from decimal import Decimal
    from python_service.models import OddsData
    odds1 = {"TestOdds": OddsData(win=Decimal("3.0"), source="TestOdds", last_updated=datetime.now())}
    odds2 = {"TestOdds": OddsData(win=Decimal("4.0"), source="TestOdds", last_updated=datetime.now())}
    odds3 = {"TestOdds": OddsData(win=Decimal("5.0"), source="TestOdds", last_updated=datetime.now())}
    odds4 = {"TestOdds": OddsData(win=Decimal("6.0"), source="TestOdds", last_updated=datetime.now())}
    create_race.runners = [
        Runner(number=1, name='A', odds=odds1, scratched=False),
        Runner(number=2, name='B', odds=odds2, scratched=False),
        Runner(number=3, name='C', odds=odds3, scratched=False),
        Runner(number=4, name='D', odds=odds4, scratched=False)
    ]
    assert analyzer.is_race_qualified(create_race) is True

# New test cases for edge-case hardening
def test_rejects_with_fewer_than_three_runners(analyzer, create_race):
    from decimal import Decimal
    from python_service.models import OddsData
    odds1 = {"TestOdds": OddsData(win=Decimal("3.0"), source="TestOdds", last_updated=datetime.now())}
    odds2 = {"TestOdds": OddsData(win=Decimal("4.0"), source="TestOdds", last_updated=datetime.now())}
    create_race.runners = [
        Runner(number=1, name='A', odds=odds1, scratched=False),
        Runner(number=2, name='B', odds=odds2, scratched=False)
    ]
    assert analyzer.is_race_qualified(create_race) is False

def test_rejects_if_scratched_runners_reduce_field_below_three(analyzer, create_race):
    from decimal import Decimal
    from python_service.models import OddsData
    odds1 = {"TestOdds": OddsData(win=Decimal("3.0"), source="TestOdds", last_updated=datetime.now())}
    odds2 = {"TestOdds": OddsData(win=Decimal("4.0"), source="TestOdds", last_updated=datetime.now())}
    odds3 = {"TestOdds": OddsData(win=Decimal("5.0"), source="TestOdds", last_updated=datetime.now())}
    create_race.runners = [
        Runner(number=1, name='A', odds=odds1, scratched=False),
        Runner(number=2, name='B', odds=odds2, scratched=False),
        Runner(number=3, name='C', odds=odds3, scratched=True) # Scratched
    ]
    assert analyzer.is_race_qualified(create_race) is False

def test_handles_empty_runner_list(analyzer, create_race):
    race = create_race
    race.runners = []
    assert analyzer.is_race_qualified(race) is False

def test_handles_none_race_object(analyzer):
    assert analyzer.is_race_qualified(None) is False