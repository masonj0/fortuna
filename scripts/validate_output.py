#!/usr/bin/env python3
"""Validate pipeline output files."""

import json
import sys
from pathlib import Path


def validate_races_file(filepath: Path) -> tuple[bool, list[str]]:
    """Validate a races JSON file."""
    errors = []

    try:
        with open(filepath) as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]
    except FileNotFoundError:
        return False, [f"File not found: {filepath}"]

    if "races" not in data:
        errors.append("Missing 'races' field")
        return False, errors

    races = data["races"]
    if not isinstance(races, list):
        errors.append("'races' should be an array")
        return False, errors

    required_fields = ["id", "venue", "race_number", "runners"]

    for i, race in enumerate(races[:10]):  # Check first 10
        for field in required_fields:
            if field not in race:
                errors.append(f"Race {i}: missing '{field}'")

    return len(errors) == 0, errors


def main():
    print("=" * 60)
    print("OUTPUT VALIDATION")
    print("=" * 60)

    files = [
        ("qualified_races.json", True),
        ("raw_race_data.json", False),
    ]

    all_valid = True

    for filename, required in files:
        filepath = Path(filename)
        print(f"\n→ {filename}")

        if not filepath.exists():
            if required:
                print(f"  ❌ Required file not found")
                all_valid = False
            else:
                print(f"  ⚠️ Optional file not found")
            continue

        valid, errors = validate_races_file(filepath)

        if valid:
            with open(filepath) as f:
                data = json.load(f)
            race_count = len(data.get("races", []))
            print(f"  ✅ Valid ({race_count} races)")
        else:
            print(f"  ❌ Invalid")
            for err in errors[:5]:
                print(f"     - {err}")
            all_valid = False

    print("\n" + "=" * 60)
    if all_valid:
        print("✅ All validations passed")
        return 0
    else:
        print("❌ Validation failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
