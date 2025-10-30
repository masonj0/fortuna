# Test suite for Pydantic models, resurrected from attic/legacy_tests_pre_triage/checkmate_v7/test_models.py
import pytest
from pydantic import ValidationError
from python_service.models import Race, Runner
import datetime

def test_runner_model_creation():
    """Tests basic successful creation of the Runner model."""
    from datetime import datetime
    from decimal import Decimal
    from python_service.models import OddsData
    odds_data = {"TestOdds": OddsData(win=Decimal("6.0"), source="TestOdds", last_updated=datetime.now())}
    runner = Runner(number=5, name='Test Horse', odds=odds_data, scratched=False)
    assert runner.number == 5
    assert runner.name == 'Test Horse'
    assert not runner.scratched

def test_race_model_with_valid_runners():
    """Tests basic successful creation of the Race model."""
    from datetime import datetime
    from decimal import Decimal
    from python_service.models import OddsData
    odds1 = {"TestOdds": OddsData(win=Decimal("3.0"), source="TestOdds", last_updated=datetime.now())}
    odds2 = {"TestOdds": OddsData(win=Decimal("4.0"), source="TestOdds", last_updated=datetime.now())}
    runner1 = Runner(number=1, name='A', odds=odds1, scratched=False)
    runner2 = Runner(number=2, name='B', odds=odds2, scratched=False)
    race = Race(
        id='test-race-1',
        venue='TEST',
        race_number=1,
        start_time=datetime.now(),
        runners=[runner1, runner2],
        source='test'
    )
    assert race.venue == 'TEST'
    assert len(race.runners) == 2

def test_model_validation_fails_on_missing_required_field():
    """Ensures Pydantic's validation fires for missing required fields."""
    with pytest.raises(ValidationError):
        # 'name' is a required field for a Runner
        Runner(number=3, odds='3/1', scratched=False)

    with pytest.raises(ValidationError):
        # 'venue' is a required field for a Race
        Race(
            id='test-race-2',
            race_number=2,
            start_time=datetime.datetime.now(),
            runners=[],
            source='test'
        )