import sys
import time
import requests
import os
from datetime import datetime

def wait_for_backend(url, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            requests.get(f"{url}/health", timeout=1)
            return True
        except:
            time.sleep(1)
    return False

def fetch_news():
    base_url = "http://127.0.0.1:8000"
    print(f"🗞️ Connecting to News Engine at {base_url}...")

    if not wait_for_backend(f"{base_url}/api"):
        print("❌ Backend failed to wake up.")
        sys.exit(1)

    # 1. Fetch Races (Adjust endpoint if your filter logic is specific)
    try:
        # Try the main races endpoint
        resp = requests.get(f"{base_url}/api/races")
        data = resp.json()
    except Exception as e:
        print(f"❌ Failed to fetch news: {e}")
        sys.exit(1)

    # 2. Generate Markdown Report
    report = []
    report.append(f"# 🏇 Fortuna Racing News")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    report.append("")

    # Handle list vs dict response
    items = data if isinstance(data, list) else data.get('items', [])

    if not items:
        report.append("### 📭 No races found matching filters.")
    else:
        report.append(f"### ⚡ Found {len(items)} Active Events")
        report.append("| Time | Venue | Race | Runners | Status |")
        report.append("| :--- | :--- | :--- | :---: | :--- |")

        for race in items[:20]: # Limit to top 20 to keep UI clean
            # Normalize fields based on your schema
            venue = race.get('venue') or race.get('meeting_name') or "Unknown"
            name = race.get('name') or race.get('race_name') or f"Race {race.get('number')}"
            time_str = race.get('start_time') or race.get('advertised_start') or "TBD"
            runners = len(race.get('runners', []) or [])
            status = race.get('status') or "OPEN"

            # Make status pretty
            status_icon = "🟢" if status.lower() == "open" else "🔴"

            report.append(f"| {time_str} | **{venue}** | {name} | {runners} | {status_icon} {status} |")

    # 3. Output to GitHub Summary
    markdown_content = "\n".join(report)

    # Write to the special GitHub environment file
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(markdown_content)

    # Also print to console for logs
    print(markdown_content)

if __name__ == "__main__":
    fetch_news()
