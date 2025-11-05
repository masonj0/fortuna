import pytest
from pydantic import ValidationError

from python_service.models import Race


def test_race_model_valid_data():
    """Tests that the Race model can be created with valid data."""
    race_data = {
        "id": "test_race_123",
        "venue": "Test Park",
        "race_number": 1,
        "start_time": "2025-10-20T12:00:00Z",
        "runners": [],
        "source": "test_source",
    }
    race = Race(**race_data)
    assert race.id == "test_race_123"
    assert race.venue == "Test Park"


def test_race_model_invalid_data():
    """Tests that the Race model raises a ValidationError with invalid data."""
    invalid_race_data = {
        "id": "test_race_456",
        "venue": 12345,  # Invalid type
        "race_number": "two",  # Invalid type
        "start_time": "not-a-date",
        "runners": "not-a-list",
        "source": "test_source",
    }
    with pytest.raises(ValidationError):
        Race(**invalid_race_data)
