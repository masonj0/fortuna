#!/usr/bin/env python
"""
Fortuna Adapter-Aware Race Report Query Script

This script:
1. Starts the backend server
2. Queries adapter status to identify key-requiring adapters
3. Disables adapters that require API keys
4. Fetches race data from key-free adapters only
5. Generates HTML report
6. Cleans up gracefully

The advantage: Works without ANY API keys! Only uses adapters that need no authentication.
"""

import json
import os
import sys
import time
import subprocess
import requests
from datetime import datetime

# Configuration
HEALTH_ENDPOINT = "http://127.0.0.1:8000/api/health"
ADAPTERS_STATUS_ENDPOINT = "http://127.0.0.1:8000/api/adapters/status"
API_ENDPOINT = "http://127.0.0.1:8000/api/races/qualified/tiny_field_trifecta"
TEMPLATE_PATH = "scripts/templates/race_report_template.html"
OUTPUT_PATH = "race-report.html"
JSON_OUTPUT_PATH = "qualified_races.json"

# Timeouts (in seconds)
INITIAL_WAIT = 5
HEALTH_CHECK_TIMEOUT = 60
HEALTH_CHECK_INTERVAL = 5
API_QUERY_TIMEOUT = 30


def log(message, level="INFO"):
    """Print timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}
    print(f"[{timestamp}] {emoji.get(level, '•')} {message}")


def start_server():
    """Starts the backend server in a background process."""
    log("Starting backend server...", "INFO")

    try:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "web_service.backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        log(f"Backend process started (PID: {proc.pid})", "SUCCESS")

        # Give server initial time to start
        log(f"Waiting {INITIAL_WAIT} seconds for server initialization...", "INFO")
        time.sleep(INITIAL_WAIT)

        return proc
    except Exception as e:
        log(f"Failed to start server: {e}", "ERROR")
        return None


def wait_for_health(timeout_seconds=HEALTH_CHECK_TIMEOUT):
    """
    Poll health endpoint until backend responds or timeout.

    Args:
        timeout_seconds: Maximum time to wait in seconds

    Returns:
        True if healthy, False if timeout
    """
    log(f"Checking backend health (timeout: {timeout_seconds}s)...", "INFO")

    start_time = time.time()
    attempt = 0

    while True:
        elapsed = time.time() - start_time
        if elapsed > timeout_seconds:
            log(f"Health check timeout after {elapsed:.0f} seconds", "ERROR")
            return False

        attempt += 1
        try:
            response = requests.get(HEALTH_ENDPOINT, timeout=5)
            if response.status_code == 200:
                log(f"Backend is healthy! (attempt {attempt}, {elapsed:.0f}s)", "SUCCESS")
                return True
        except requests.RequestException:
            pass  # Will retry

        log(f"Health check attempt {attempt} failed, retrying in {HEALTH_CHECK_INTERVAL}s...", "WARNING")
        time.sleep(HEALTH_CHECK_INTERVAL)


def get_adapter_status():
    """
    Get status of all adapters and identify which ones require API keys.

    Returns:
        Tuple of (all_adapters, key_required_adapters, key_free_adapters)
    """
    log("Fetching adapter status...", "INFO")

    try:
        response = requests.get(ADAPTERS_STATUS_ENDPOINT, timeout=API_QUERY_TIMEOUT)
        response.raise_for_status()
        adapters = response.json()

        if not isinstance(adapters, list):
            adapters = adapters.get("adapters", [])

        # Categorize adapters
        key_required = []
        key_free = []

        for adapter in adapters:
            adapter_name = adapter.get("name") or adapter.get("adapter_name") or "Unknown"
            requires_key = adapter.get("requires_api_key") or adapter.get("api_key_required") or False

            if requires_key:
                key_required.append(adapter_name)
            else:
                key_free.append(adapter_name)

        log(f"Found {len(adapters)} total adapters", "SUCCESS")
        log(f"  🔐 {len(key_required)} adapters require API keys (will be SKIPPED)", "WARNING")
        log(f"  ✅ {len(key_free)} adapters are key-free (will be used)", "SUCCESS")

        if key_required:
            log(f"Skipping key-required adapters: {', '.join(key_required[:5])}", "INFO")
            if len(key_required) > 5:
                log(f"  ... and {len(key_required) - 5} more", "INFO")

        return adapters, key_required, key_free

    except requests.exceptions.Timeout:
        log(f"Adapter status query timed out after {API_QUERY_TIMEOUT} seconds", "WARNING")
        return [], [], []
    except requests.exceptions.ConnectionError as e:
        log(f"Connection error: {e}", "WARNING")
        return [], [], []
    except requests.exceptions.HTTPError as e:
        log(f"HTTP error: {response.status_code}", "WARNING")
        return [], [], []
    except Exception as e:
        log(f"Unexpected error fetching adapter status: {e}", "WARNING")
        return [], [], []


def disable_key_required_adapters(key_required_adapters):
    """
    Attempt to disable adapters that require API keys.

    Args:
        key_required_adapters: List of adapter names to disable

    Returns:
        True if successful, False otherwise
    """
    if not key_required_adapters:
        log("No adapters to disable", "INFO")
        return True

    log(f"Attempting to disable {len(key_required_adapters)} key-required adapters...", "INFO")

    disable_endpoint = "http://127.0.0.1:8000/api/adapters/disable"

    try:
        for adapter_name in key_required_adapters:
            payload = {"adapter_name": adapter_name}
            try:
                response = requests.post(disable_endpoint, json=payload, timeout=5)
                if response.status_code == 200:
                    log(f"  ✅ Disabled: {adapter_name}", "INFO")
                else:
                    log(f"  ⚠️ Could not disable {adapter_name} (status: {response.status_code})", "WARNING")
            except requests.RequestException as e:
                log(f"  ⚠️ Could not disable {adapter_name}: {e}", "WARNING")

        return True
    except Exception as e:
        log(f"Error disabling adapters: {e}", "WARNING")
        return False


def query_races(timeout_seconds=API_QUERY_TIMEOUT):
    """
    Queries the API for qualified races (from key-free adapters only).

    Args:
        timeout_seconds: Request timeout in seconds

    Returns:
        Race data dict or None if failed
    """
    log(f"Querying API for qualified races...", "INFO")

    try:
        response = requests.get(API_ENDPOINT, timeout=timeout_seconds)
        response.raise_for_status()

        data = response.json()
        race_count = len(data.get("races", []))
        log(f"Successfully retrieved {race_count} races", "SUCCESS")

        if race_count == 0:
            log("Note: No races match the filter criteria at this time", "INFO")

        return data

    except requests.exceptions.Timeout:
        log(f"API request timed out after {timeout_seconds} seconds", "ERROR")
        return None
    except requests.exceptions.ConnectionError as e:
        log(f"Connection error: {e}", "ERROR")
        return None
    except requests.exceptions.HTTPError as e:
        log(f"HTTP error: {response.status_code}", "ERROR")
        return None
    except json.JSONDecodeError:
        log("API response was not valid JSON", "ERROR")
        return None
    except Exception as e:
        log(f"Unexpected error during query: {e}", "ERROR")
        return None


def generate_report(race_data):
    """
    Injects race data into the HTML template.

    Args:
        race_data: Dictionary containing race information

    Returns:
        True if successful, False otherwise
    """
    log(f"Generating HTML report...", "INFO")

    try:
        # Check if template exists
        if not os.path.exists(TEMPLATE_PATH):
            log(f"Template not found at {TEMPLATE_PATH}", "ERROR")
            log("Creating minimal fallback HTML...", "WARNING")
            fallback_html = f"<pre>{json.dumps(race_data, indent=2)}</pre>"
            with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
                f.write(fallback_html)
            return True

        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            template = f.read()

        # Replace placeholder with race data
        report_html = template.replace("__RACE_DATA_PLACEHOLDER__", json.dumps(race_data))

        # Write report
        with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write(report_html)

        log(f"Report saved to {OUTPUT_PATH}", "SUCCESS")
        return True

    except Exception as e:
        log(f"Failed to generate report: {e}", "ERROR")
        return False


def save_json_data(race_data):
    """
    Save race data to JSON file.

    Args:
        race_data: Dictionary containing race information

    Returns:
        True if successful, False otherwise
    """
    try:
        with open(JSON_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(race_data, f, indent=2)
        log(f"JSON data saved to {JSON_OUTPUT_PATH}", "SUCCESS")
        return True
    except Exception as e:
        log(f"Failed to save JSON: {e}", "ERROR")
        return False


def main():
    """Main entry point."""
    log("=== Fortuna Adapter-Aware Race Report Generator ===", "INFO")

    server_process = None

    try:
        # Step 1: Start server
        server_process = start_server()
        if not server_process:
            log("Failed to start backend server", "ERROR")
            return 1

        # Step 2: Wait for health
        if not wait_for_health(HEALTH_CHECK_TIMEOUT):
            log("Backend did not become healthy in time", "ERROR")
            return 1

        # Step 3: Get adapter status (optional - may not be implemented)
        adapters, key_required, key_free = get_adapter_status()

        # Step 4: Disable key-required adapters (optional - may not be implemented)
        if key_required:
            disable_key_required_adapters(key_required)

        # Step 5: Query races
        race_data = query_races(API_QUERY_TIMEOUT)
        if race_data is None:
            log("Failed to fetch race data", "ERROR")
            return 1

        # Step 6: Save JSON
        save_json_data(race_data)

        # Step 7: Generate report
        if not generate_report(race_data):
            log("Failed to generate report", "ERROR")
            return 1

        log("=== SUCCESS ===", "SUCCESS")
        return 0

    except Exception as e:
        log(f"Unexpected error in main: {e}", "ERROR")
        return 1

    finally:
        # Step 8: Cleanup
        if server_process:
            log("Stopping backend server...", "INFO")
            try:
                server_process.terminate()
                try:
                    server_process.wait(timeout=5)
                    log("Backend stopped cleanly", "SUCCESS")
                except subprocess.TimeoutExpired:
                    log("Backend did not stop, forcing termination...", "WARNING")
                    server_process.kill()
                    server_process.wait()
            except Exception as e:
                log(f"Error during cleanup: {e}", "WARNING")


if __name__ == "__main__":
    sys.exit(main())
