import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_service.validation.validator import SchemaValidator

def main():
    """Validates the output files."""
    validator = SchemaValidator()

    files_to_validate = [
        ("qualified_races.json", "qualified_races"),
        ("raw_race_data.json", "raw_race_data"),
    ]

    all_valid = True
    for file_path, schema_name in files_to_validate:
        try:
            with open(file_path) as f:
                data = json.load(f)
            result = validator.validate(data, schema_name)

            print(f"\n{'='*60}")
            print(f"Validation: {file_path}")
            print(f"{'='*60}")
            print(f"Valid: {result.valid}")
            print(f"Errors: {len(result.errors)}")
            print(f"Warnings: {len(result.warnings)}")

            for error in result.errors[:5]:
                print(f"  ❌ {error}")
            for warning in result.warnings[:3]:
                print(f"  ⚠️ {warning}")

            if not result.valid:
                all_valid = False

        except FileNotFoundError:
            print(f"⚠️ {file_path} not found, skipping validation")

    if not all_valid:
        print("\n❌ Validation failed!")
        sys.exit(1)
    else:
        print("\n✅ All validations passed!")

if __name__ == "__main__":
    main()
