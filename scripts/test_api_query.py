#!/usr/bin/env python
"""
Simple Fortuna Race Data Query Script

This is a lightweight script for testing the race data API locally.
It queries for filtered races and outputs the results.

Usage:
  python scripts/test_api_query.py

The script expects the backend to be running on http://127.0.0.1:8000
"""

import json
import os
import sys
import time
from datetime import datetime

try:
    import requests
except ImportError:
    print("❌ Error: 'requests' module not found.")
    print("Install it with: pip install requests")
    sys.exit(1)


# Configuration
API_BASE_URL = os.getenv("FORTUNA_API_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("API_KEY", "a_secure_test_api_key_that_is_long_enough")
TIMEOUT = 10


def log(message, level="INFO"):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}
    print(f"[{timestamp}] {emoji.get(level, '•')} {message}")


def check_backend_health():
    """Check if the backend API is responding."""
    log("Checking backend health...", "INFO")
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/health",
            timeout=TIMEOUT,
            headers={"X-API-Key": API_KEY},
        )
        if response.status_code == 200:
            log("Backend is healthy", "SUCCESS")
            return True
    except requests.RequestException as e:
        log(f"Health check failed: {e}", "ERROR")
        return False
    return False


def fetch_filtered_races():
    """Fetch trifecta-qualified races from the API."""
    endpoint = "/api/races/qualified/trifecta"
    url = f"{API_BASE_URL}{endpoint}"

    log(f"Querying {url}", "INFO")

    try:
        headers = {"X-API-Key": API_KEY}
        response = requests.get(url, timeout=TIMEOUT, headers=headers)
        response.raise_for_status()

        data = response.json()
        races = data.get("races", [])

        log(f"Retrieved {len(races)} qualified races", "SUCCESS")
        return data

    except requests.exceptions.Timeout:
        log(f"Request timed out after {TIMEOUT} seconds", "ERROR")
        return None
    except requests.exceptions.ConnectionError as e:
        log(f"Connection error: {e}", "ERROR")
        log(f"Is the backend running at {API_BASE_URL}?", "WARNING")
        return None
    except requests.exceptions.HTTPError as e:
        log(f"HTTP error: {response.status_code} {response.reason}", "ERROR")
        return None
    except json.JSONDecodeError:
        log("Response was not valid JSON", "ERROR")
        return None
    except Exception as e:
        log(f"Unexpected error: {e}", "ERROR")
        return None


def display_races(races_data):
    """Pretty-print the races to console."""
    if not races_data:
        log("No data to display", "WARNING")
        return

    races = races_data.get("races", [])

    print("\\n" + "=" * 80)
    print(f"FORTUNA FILTERED RACE REPORT - {len(races)} Races")
    print("=" * 80 + "\\n")

    if not races:
        print("❌ No qualified races found at this time.\\n")
        return

    for idx, race in enumerate(races, 1):
        venue = race.get("venue", "Unknown")
        race_num = race.get("race_number", "?")
        start_time = race.get("startTime", "N/A")
        runners = race.get("runners", [])

        print(f"[{idx}] {venue} - Race {race_num}")
        print(f"    Post Time: {start_time}")
        print(f"    Runners: {len(runners)}")
        print("\\n    Horse Name                  | Win Odds | Best Source")
        print("    " + "-" * 60)

        for runner in runners:
            name = runner.get("name", "Unknown")
            odds_data = runner.get("odds", {})

            # Find best win odds
            best_odds = "N/A"
            best_source = "N/A"
            if odds_data:
                best_val = 0.0
                for source, odds_obj in odds_data.items():
                    win_odds = odds_obj.get("win", 0.0)
                    if win_odds > best_val:
                        best_val = win_odds
                        best_odds = f"{best_val:.2f}"
                        best_source = source

            # Truncate long names
            display_name = name[:28]
            print(f"    {display_name:28} | {best_odds:>8} | {best_source}")

        print()


def save_to_json(races_data, filename="qualified_races.json"):
    """Save race data to JSON file."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(races_data, f, indent=2)
        log(f"Saved race data to {filename}", "SUCCESS")
        return True
    except Exception as e:
        log(f"Failed to save JSON: {e}", "ERROR")
        return False


def main():
    """Main entry point."""
    log("=== Fortuna Race Data Query ===", "INFO")
    log(f"API URL: {API_BASE_URL}", "INFO")

    # Check backend health
    if not check_backend_health():
        log("Backend is not responding", "ERROR")
        log("Make sure to start the backend with:", "WARNING")
        log("  python -m uvicorn web_service.backend.main:app --port 8000", "WARNING")
        return 1

    # Fetch races
    races_data = fetch_filtered_races()
    if not races_data:
        log("Failed to fetch race data", "ERROR")
        return 1

    # Display results
    display_races(races_data)

    # Save to JSON
    save_to_json(races_data)

    log("Complete", "SUCCESS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
