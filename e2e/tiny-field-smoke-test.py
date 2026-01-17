import json
import os
import sys
import requests

API_KEY = os.environ.get("API_KEY", "a_secure_test_api_key_that_is_long_enough")
BASE_URL = "http://127.0.0.1:8000"

def main():
    """
    Runs a smoke test against the tiny_field_trifecta endpoint.
    """
    print("--- Running Tiny Field Smoke Test ---")

    headers = {"X-API-Key": API_KEY}
    url = f"{BASE_URL}/api/races/qualified/tiny_field_trifecta"

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()

        print(f"Successfully received data with {len(data.get('races', []))} qualified races.")

        # Verify the analyzer configuration
        criteria = data.get("analysis_metadata", {})
        max_field_size = criteria.get("max_field_size")

        if max_field_size == 6:
            print(f"[SUCCESS] Analyzer correctly configured with max_field_size={max_field_size}")
            sys.exit(0)
        else:
            print(f"[FAILURE] Incorrect max_field_size. Expected 6, got {max_field_size}")
            sys.exit(1)

    except requests.exceptions.RequestException as e:
        print(f"[FAILURE] Could not connect to the API: {e}")
        sys.exit(1)
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[FAILURE] Could not parse the API response: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
