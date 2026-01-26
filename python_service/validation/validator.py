"""
Schema validation with detailed error reporting.
"""

import json
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

try:
    import jsonschema
    from jsonschema import Draft7Validator, ValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

from .schemas import QUALIFIED_RACES_SCHEMA, RAW_RACE_DATA_SCHEMA, RACE_SCHEMA
from ..observability import get_logger, metrics

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of schema validation."""
    valid: bool
    errors: List[str]
    warnings: List[str]
    stats: Dict[str, Any]


class SchemaValidator:
    """
    Validates pipeline outputs against JSON schemas.
    """

    SCHEMAS = {
        "qualified_races": QUALIFIED_RACES_SCHEMA,
        "raw_race_data": RAW_RACE_DATA_SCHEMA,
        "race": RACE_SCHEMA,
    }

    def __init__(self):
        if not HAS_JSONSCHEMA:
            logger.warning("jsonschema not installed, validation disabled")

    def validate(
        self,
        data: Any,
        schema_name: str,
        strict: bool = False,
    ) -> ValidationResult:
        """
        Validate data against a named schema.

        Args:
            data: Data to validate
            schema_name: Name of schema from SCHEMAS dict
            strict: If True, treat warnings as errors

        Returns:
            ValidationResult with details
        """
        if not HAS_JSONSCHEMA:
            return ValidationResult(
                valid=True,
                errors=[],
                warnings=["Validation skipped: jsonschema not installed"],
                stats={}
            )

        schema = self.SCHEMAS.get(schema_name)
        if not schema:
            return ValidationResult(
                valid=False,
                errors=[f"Unknown schema: {schema_name}"],
                warnings=[],
                stats={}
            )

        errors = []
        warnings = []
        stats = {}

        try:
            validator = Draft7Validator(schema)
            validation_errors = list(validator.iter_errors(data))

            for error in validation_errors:
                path = " -> ".join(str(p) for p in error.absolute_path) or "root"
                message = f"{path}: {error.message}"

                # Categorize by severity
                if self._is_critical_error(error):
                    errors.append(message)
                else:
                    warnings.append(message)

            # Collect stats
            if schema_name == "qualified_races" and isinstance(data, dict):
                races = data.get("races", [])
                stats = {
                    "race_count": len(races),
                    "total_runners": sum(len(r.get("runners", [])) for r in races),
                    "venues": len(set(r.get("venue", "") for r in races)),
                }

            valid = len(errors) == 0
            if strict:
                valid = valid and len(warnings) == 0

            # Emit metrics
            metrics.inc("validation_runs", labels={"schema": schema_name})
            if not valid:
                metrics.inc("validation_failures", labels={"schema": schema_name})

            return ValidationResult(
                valid=valid,
                errors=errors,
                warnings=warnings,
                stats=stats
            )

        except Exception as e:
            logger.error(f"Validation failed: {e}")
            return ValidationResult(
                valid=False,
                errors=[f"Validation exception: {str(e)}"],
                warnings=[],
                stats={}
            )

    def _is_critical_error(self, error) -> bool:
        """Determine if a validation error is critical."""
        # Missing required fields are critical
        if "required" in error.validator:
            return True

        # Type errors on core fields are critical
        if error.validator == "type":
            critical_paths = ["id", "venue", "race_number", "runners"]
            path_str = ".".join(str(p) for p in error.absolute_path)
            return any(p in path_str for p in critical_paths)

        return False

    def validate_file(
        self,
        file_path: Path,
        schema_name: str,
        strict: bool = False,
    ) -> ValidationResult:
        """Validate a JSON file against a schema."""
        try:
            with open(file_path) as f:
                data = json.load(f)
            return self.validate(data, schema_name, strict)
        except json.JSONDecodeError as e:
            return ValidationResult(
                valid=False,
                errors=[f"Invalid JSON: {e}"],
                warnings=[],
                stats={}
            )
        except FileNotFoundError:
            return ValidationResult(
                valid=False,
                errors=[f"File not found: {file_path}"],
                warnings=[],
                stats={}
            )


# Contract tests for adapters
class AdapterContractTests:
    """
    Contract tests to verify adapters produce expected output structure.
    """

    REQUIRED_RACE_FIELDS = ["id", "venue", "race_number", "start_time", "runners", "source"]
    REQUIRED_RUNNER_FIELDS = ["number", "name"]

    @classmethod
    async def test_adapter(cls, adapter, date: str) -> Tuple[bool, List[str]]:
        """
        Run contract tests on an adapter.

        Args:
            adapter: Adapter instance to test
            date: Date string for fetching

        Returns:
            Tuple of (passed, error_messages)
        """
        errors = []

        try:
            races = await adapter.get_races(date)

            if races is None:
                errors.append("Adapter returned None instead of empty list")
                return False, errors

            if not isinstance(races, list):
                errors.append(f"Expected list, got {type(races).__name__}")
                return False, errors

            for i, race in enumerate(races):
                race_errors = cls._validate_race(race, i)
                errors.extend(race_errors)

            # Log result
            logger.info(
                f"Contract test completed",
                adapter=adapter.SOURCE_NAME,
                races=len(races),
                errors=len(errors)
            )

            return len(errors) == 0, errors

        except Exception as e:
            errors.append(f"Exception during test: {e}")
            return False, errors

    @classmethod
    def _validate_race(cls, race, index: int) -> List[str]:
        """Validate a single race object."""
        errors = []
        prefix = f"Race[{index}]"

        # Check it's an object with expected interface
        for field in cls.REQUIRED_RACE_FIELDS:
            if not hasattr(race, field):
                errors.append(f"{prefix}: Missing required field '{field}'")

        # Validate runners
        if hasattr(race, 'runners'):
            if not isinstance(race.runners, list):
                errors.append(f"{prefix}: 'runners' should be a list")
            else:
                for j, runner in enumerate(race.runners):
                    for field in cls.REQUIRED_RUNNER_FIELDS:
                        if not hasattr(runner, field):
                            errors.append(f"{prefix}.Runner[{j}]: Missing '{field}'")

        return errors
