#!/usr/bin/env python3
# scripts/validate_output.py
"""
Validate pipeline output files against schemas.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple

# Simplified schema definitions (inline to avoid import issues)
RACE_SCHEMA = {
    "required_fields": ["id", "venue", "race_number", "start_time", "runners", "source"],
    "runner_required": ["number", "name"],
}


def validate_race(race: Dict, index: int) -> List[str]:
    """Validate a single race object."""
    errors = []
    prefix = f"races[{index}]"

    for field in RACE_SCHEMA["required_fields"]:
        if field not in race:
            errors.append(f"{prefix}: missing required field '{field}'")

    if "runners" in race:
        if not isinstance(race["runners"], list):
            errors.append(f"{prefix}.runners: should be a list")
        else:
            for j, runner in enumerate(race["runners"]):
                for field in RACE_SCHEMA["runner_required"]:
                    if field not in runner:
                        errors.append(f"{prefix}.runners[{j}]: missing '{field}'")

    return errors


def validate_qualified_races(data: Dict) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Validate qualified_races.json structure."""
    errors = []
    warnings = []
    stats = {}

    # Check top-level fields
    if "races" not in data:
        errors.append("Missing 'races' array")
        return False, errors, stats

    races = data["races"]
    if not isinstance(races, list):
        errors.append("'races' should be an array")
        return False, errors, stats

    stats["race_count"] = len(races)
    stats["venues"] = set()
    stats["total_runners"] = 0

    # Validate each race
    for i, race in enumerate(races):
        race_errors = validate_race(race, i)
        errors.extend(race_errors)

        if "venue" in race:
            stats["venues"].add(race["venue"])
        if "runners" in race and isinstance(race["runners"], list):
            stats["total_runners"] += len(race["runners"])

    stats["venues"] = list(stats["venues"])
    stats["venue_count"] = len(stats["venues"])

    # Warnings
    if len(races) == 0:
        warnings.append("No races in output")

    return len(errors) == 0, errors + warnings, stats


def validate_raw_race_data(data: Dict) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Validate raw_race_data.json structure."""
    errors = []
    stats = {}

    if "races" not in data:
        errors.append("Missing 'races' array")
        return False, errors, stats

    races = data["races"]
    stats["race_count"] = len(races) if isinstance(races, list) else 0

    return len(errors) == 0, errors, stats


def main():
    """Run validation on output files."""
    print("=" * 60)
    print("OUTPUT VALIDATION")
    print("=" * 60)

    files_to_validate = [
        ("qualified_races.json", validate_qualified_races),
        ("raw_race_data.json", validate_raw_race_data),
    ]

    all_valid = True

    for filename, validator in files_to_validate:
        filepath = Path(filename)
        print(f"\n→ Validating {filename}...")

        if not filepath.exists():
            print(f"  ⚠️ File not found (skipping)")
            continue

        try:
            with open(filepath) as f:
                data = json.load(f)

            valid, messages, stats = validator(data)

            if valid:
                print(f"  ✅ Valid")
            else:
                print(f"  ❌ Invalid")
                all_valid = False

            # Print stats
            for key, value in stats.items():
                if isinstance(value, list) and len(value) > 5:
                    print(f"     {key}: {len(value)} items")
                else:
                    print(f"     {key}: {value}")

            # Print errors/warnings
            for msg in messages[:10]:  # Limit output
                if "missing" in msg.lower() or "should be" in msg.lower():
                    print(f"     ❌ {msg}")
                else:
                    print(f"     ⚠️ {msg}")

            if len(messages) > 10:
                print(f"     ... and {len(messages) - 10} more issues")

        except json.JSONDecodeError as e:
            print(f"  ❌ Invalid JSON: {e}")
            all_valid = False
        except Exception as e:
            print(f"  ❌ Error: {e}")
            all_valid = False

    print("\n" + "=" * 60)
    if all_valid:
        print("✅ All validations passed")
        return 0
    else:
        print("❌ Some validations failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
