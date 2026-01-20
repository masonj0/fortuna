#!/usr/bin/env python
"""
Fortuna Unified Race Reporter

Generates HTML, JSON, and Markdown summary reports for GitHub Actions
by directly invoking the OddsEngine and AnalyzerEngine without a live API.
"""

import asyncio
import json
import os
import sys
from datetime import datetime

# Ensure the project root is in the path to allow for direct imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now that the path is set, we can import our modules
from web_service.backend.engine import OddsEngine
from web_service.backend.analyzer import AnalyzerEngine
from web_service.backend.config import get_settings
from web_service.backend.models import Race

# --- Configuration ---
TEMPLATE_PATH = "scripts/templates/race_report_template.html"
HTML_OUTPUT_PATH = "race-report.html"
JSON_OUTPUT_PATH = "qualified_races.json"
MARKDOWN_SUMMARY_PATH = "github_summary.md"


def log(message, level="INFO"):
    """Print a timestamped log message."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    emoji = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARNING": "⚠️"}
    print(f"[{timestamp}] {emoji.get(level, '•')} {message}")
    sys.stdout.flush()


def generate_html_report(race_data: dict):
    """Generates the HTML report from a template."""
    log("Generating HTML report...")
    try:
        if not os.path.exists(TEMPLATE_PATH):
            log(f"Template not found at {TEMPLATE_PATH}. Cannot generate HTML report.", "ERROR")
            return

        with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
            template = f.read()

        report_html = template.replace("__RACE_DATA_PLACEHOLDER__", json.dumps(race_data))

        with open(HTML_OUTPUT_PATH, "w", encoding="utf-8") as f:
            f.write(report_html)

        log(f"Successfully generated HTML report at {HTML_OUTPUT_PATH}", "SUCCESS")
    except Exception as e:
        log(f"Failed to generate HTML report: {e}", "ERROR")


def generate_markdown_summary(races: list):
    """Generates a Markdown summary for the GitHub Actions UI."""
    log("Generating Markdown summary...")
    report = [
        "# 🐴 Fortuna Race Report",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
        ""
    ]

    if not races:
        report.append("### 🔭 No races found matching filters.")
    else:
        report.append(f"### ⚡ Found {len(races)} Qualified Races")
        report.append("| Score | Time | Venue | Race | Runners |")
        report.append("| :---: | :--- | :--- | :--- | :---: |")

        for race in races[:20]:  # Limit to top 20 for summary
            start_time_dt = race.start_time if isinstance(race.start_time, datetime) else datetime.fromisoformat(race.start_time)
            time_str = start_time_dt.strftime('%H:%M')
            score = f"{race.qualification_score:.1f}" if race.qualification_score is not None else "N/A"
            report.append(f"| {score} | {time_str} | **{race.venue}** | {race.race_number} | {len(race.runners)} |")

    markdown_content = "\n".join(report)

    try:
        with open(MARKDOWN_SUMMARY_PATH, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        log(f"Successfully generated Markdown summary at {MARKDOWN_SUMMARY_PATH}", "SUCCESS")
    except Exception as e:
        log(f"Failed to write Markdown summary: {e}", "ERROR")


async def main():
    """Main entry point for the script."""
    log("=== Fortuna Unified Race Reporter ===")

    settings = get_settings()
    odds_engine = OddsEngine(config=settings)
    analyzer_engine = AnalyzerEngine()

    today_str = datetime.now().strftime("%Y-%m-%d")

    try:
        log(f"Fetching all race data for {today_str}...")
        aggregated_data = await odds_engine.fetch_all_odds(today_str)

        all_races_raw = aggregated_data.get("races", [])
        if not all_races_raw:
            log("No races returned from OddsEngine. Exiting.", "WARNING")
            return

        # Pydantic validation
        all_races = [Race(**r) for r in all_races_raw]
        log(f"Successfully fetched and validated {len(all_races)} races.")

        log("Analyzing races with 'tiny_field_trifecta' analyzer...")
        analyzer = analyzer_engine.get_analyzer("tiny_field_trifecta")
        result = analyzer.qualify_races(all_races)

        qualified_races = result.get("races", [])
        criteria = result.get("criteria", {})
        log(f"Found {len(qualified_races)} qualified races.", "SUCCESS")

        # Prepare data for reports
        report_data = {
            "races": [r.model_dump(mode='json') for r in qualified_races],
            "analysis_metadata": criteria,
            "timestamp": datetime.now().isoformat()
        }

        # Generate all outputs
        with open(JSON_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        log(f"Successfully saved JSON data to {JSON_OUTPUT_PATH}", "SUCCESS")

        generate_html_report(report_data)
        generate_markdown_summary(qualified_races)

    except Exception as e:
        log(f"An unexpected error occurred: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        await odds_engine.close()
        log("--- Reporter finished ---")


if __name__ == "__main__":
    asyncio.run(main())
