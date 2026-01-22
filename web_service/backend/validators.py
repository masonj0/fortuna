# web_service/backend/validators.py
from pydantic import BaseModel, validator, Field
from typing import Any
from datetime import datetime, timedelta

class RaceValidator(BaseModel):
    """Strict validation for race data."""
    venue: str = Field(..., min_length=1)
    race_number: int = Field(..., ge=1, le=20)
    start_time: datetime
    runners: list[dict] = Field(..., min_items=2)

    @validator('runners')
    def validate_runners(cls, v):
        """Ensure runners have required fields."""
        for runner in v:
            if not runner.get('name'):
                raise ValueError("Runner missing name")
            if 'odds' not in runner and 'number' not in runner:
                raise ValueError("Runner missing odds or number")
        return v

    @validator('start_time')
    def validate_time_reasonable(cls, v):
        """Check race time is reasonable (not too far in past/future)."""
        now = datetime.utcnow()
        if v.tzinfo is None:
            v = v.replace(tzinfo=now.tzinfo)

        if v < now - timedelta(hours=2):
            raise ValueError("Race time too far in past")
        if v > now + timedelta(days=7):
            raise ValueError("Race time too far in future")
        return v

class DataValidationPipeline:
    """Validates and cleans data between adapter and parser."""

    @staticmethod
    def validate_raw_response(adapter_name: str, raw_data: Any) -> tuple[bool, str]:
        """Quick validation of raw adapter response."""
        if raw_data is None:
            return False, "Null response"

        if isinstance(raw_data, dict):
            if not raw_data:
                return False, "Empty dict"
            if 'error' in raw_data:
                return False, f"Error in response: {raw_data['error']}"

        if isinstance(raw_data, str):
            if len(raw_data) < 100:
                return False, "Response too short"
            if 'error' in raw_data.lower() or '404' in raw_data:
                return False, "Error indicators in HTML"

        return True, "OK"

    @staticmethod
    def validate_parsed_races(races: list) -> tuple[list, list[str]]:
        """Validate parsed races and return valid ones + warnings."""
        valid_races = []
        warnings = []

        for i, race in enumerate(races):
            try:
                # Use Pydantic validation
                RaceValidator(**race.dict())
                valid_races.append(race)
            except Exception as e:
                warnings.append(f"Race {i} validation failed: {str(e)}")

        return valid_races, warnings
