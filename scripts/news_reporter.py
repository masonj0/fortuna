#!/usr/bin/env python
"""
Fortuna News Reporter Script

Fetches racing data and displays in GitHub Actions summary as a markdown table.
Optimized for Windows runners.
"""

import sys
import time
import requests
import os
from datetime import datetime


def wait_for_backend(base_url, timeout=30):
    """Poll backend health endpoint with timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f"{base_url}/api/health", timeout=2)
            if response.status_code == 200:
                print(f"✅ Backend is healthy (took {time.time() - start:.1f}s)")
                return True
        except requests.RequestException:
            pass
        time.sleep(1)
    return False


def fetch_news():
    """Fetch and display racing news."""
    base_url = "http://127.0.0.1:8000"
    print(f"🗞️ Connecting to Racing News Engine at {base_url}...")

    if not wait_for_backend(base_url, timeout=30):
        print("❌ Backend failed to start within 30 seconds.")
        sys.exit(1)

    # Fetch races
    try:
        api_key = os.environ.get("API_KEY", "a_secure_test_api_key_that_is_long_enough")
        headers = {"X-API-Key": api_key}
        resp = requests.get(f"{base_url}/api/races", headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"❌ Failed to fetch news: {e}")
        sys.exit(1)

    # Generate report
    report = []
    report.append("# 🐴 Fortuna Racing News")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    report.append("")

    # Handle both list and dict responses
    items = data if isinstance(data, list) else data.get('races', [])

    if not items:
        report.append("### 🔭 No races found matching filters.")
    else:
        report.append(f"### ⚡ Found {len(items)} Active Events")
        report.append("| Time | Venue | Race | Runners | Status |")
        report.append("| :--- | :--- | :--- | :---: | :--- |")

        for race in items[:20]:  # Limit to top 20
            # Normalize fields
            venue = race.get('venue') or race.get('meeting_name') or "Unknown"
            name = race.get('name') or race.get('race_name') or f"Race {race.get('race_number')}"
            time_str = race.get('start_time') or race.get('advertised_start') or "TBD"
            runners = len(race.get('runners', []) or [])
            status = race.get('status') or "OPEN"

            # Make status pretty
            status_icon = "🟢" if status.lower() == "open" else "🔴"

            report.append(f"| {time_str} | **{venue}** | {name} | {runners} | {status_icon} {status} |")

    # Output to GitHub summary and console
    markdown_content = "\n".join(report)

    # Write to GitHub summary if available
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        try:
            with open(summary_file, "a", encoding="utf-8") as f:
                f.write(markdown_content)
            print("✅ Report written to GitHub summary")
        except Exception as e:
            print(f"⚠️ Could not write to GitHub summary: {e}")

    # Always print to console
    print(markdown_content)


if __name__ == "__main__":
    fetch_news()
