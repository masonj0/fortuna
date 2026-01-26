#!/usr/bin/env python3
# scripts/generate_summary.py
"""
Generate GitHub Actions step summary with runtime insights.
"""

import json
import os
from datetime import datetime
from pathlib import Path


def main():
    """Generate markdown summary."""
    lines = []

    # Header
    lines.append("## 🐴 Fortuna Race Report Summary\n")

    # Run info
    lines.append("### 📋 Run Information\n")
    lines.append(f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"**Run Number:** #{os.environ.get('GITHUB_RUN_NUMBER', 'N/A')}")
    lines.append(f"**Analyzer:** {os.environ.get('ANALYZER_TYPE', 'tiny_field_trifecta')}")
    lines.append("")

    # Race Results
    if Path("qualified_races.json").exists():
        try:
            with open("qualified_races.json") as f:
                data = json.load(f)

            races = data.get("races", [])

            lines.append("### 📊 Results\n")
            lines.append(f"**Qualified Races:** {len(races)}")

            if races:
                # Count by venue
                venues = {}
                total_runners = 0
                for race in races:
                    venue = race.get("venue", "Unknown")
                    venues[venue] = venues.get(venue, 0) + 1
                    total_runners += len(race.get("runners", []))

                lines.append(f"**Total Runners:** {total_runners}")
                lines.append(f"**Unique Venues:** {len(venues)}")
                lines.append("")

                # Top venues table
                if venues:
                    lines.append("#### Top Venues\n")
                    lines.append("| Venue | Races |")
                    lines.append("|-------|-------|")
                    for venue, count in sorted(venues.items(), key=lambda x: -x[1])[:10]:
                        lines.append(f"| {venue} | {count} |")
                    lines.append("")
        except Exception as e:
            lines.append(f"⚠️ Error reading results: {e}")
            lines.append("")
    else:
        lines.append("### ⚠️ No Results\n")
        lines.append("No qualified_races.json file was generated.")
        lines.append("")

    # Adapter Stats
    if Path("adapter_stats.json").exists():
        try:
            with open("adapter_stats.json") as f:
                stats = json.load(f)

            lines.append("### 🔌 Adapter Statistics\n")
            lines.append("| Adapter | Status | Races | Time |")
            lines.append("|---------|--------|-------|------|")

            for adapter in stats.get("adapters", []):
                name = adapter.get("name", "Unknown")
                status = "✅" if adapter.get("success") else "❌"
                races = adapter.get("race_count", 0)
                time_ms = adapter.get("duration_ms", 0)
                lines.append(f"| {name} | {status} | {races} | {time_ms:.0f}ms |")

            lines.append("")
        except Exception as e:
            pass

    # Browser Stats
    if Path("browser_selector_state.json").exists():
        try:
            with open("browser_selector_state.json") as f:
                browser_state = json.load(f)

            lines.append("### 🌐 Browser Performance\n")
            lines.append("| Backend | Success Rate | Total Attempts |")
            lines.append("|---------|--------------|----------------|")

            for backend, stats in browser_state.get("stats", {}).items():
                total = stats.get("total_attempts", 0)
                success = stats.get("successful_attempts", 0)
                rate = f"{success/total:.1%}" if total > 0 else "N/A"
                lines.append(f"| {backend} | {rate} | {total} |")

            lines.append("")
        except Exception as e:
            pass

    # Browser Verification
    if Path("browser_verification.json").exists():
        try:
            with open("browser_verification.json") as f:
                verify = json.load(f)

            lines.append("### 🧪 Browser Verification\n")
            for test_name, result in verify.get("tests", {}).items():
                status = "✅" if result.get("passed") else "❌"
                lines.append(f"- {status} **{test_name}**: {result.get('message', 'N/A')}")
            lines.append("")
        except Exception as e:
            pass

    # Canary Results
    if Path("canary_result.json").exists():
        try:
            with open("canary_result.json") as f:
                canary = json.load(f)

            status_emoji = {
                "healthy": "✅",
                "degraded": "⚠️",
                "unhealthy": "❌"
            }.get(canary.get("status"), "❓")

            lines.append("### 🐤 Canary Health\n")
            lines.append(f"**Status:** {status_emoji} {canary.get('status', 'unknown').upper()}")
            lines.append(f"**Success Rate:** {canary.get('success_rate', 'N/A')}")
            lines.append("")
        except Exception as e:
            pass

    # Errors
    errors_file = Path("errors.json")
    if errors_file.exists() and errors_file.stat().st_size > 0:
        try:
            errors = []
            with open(errors_file) as f:
                for line in f:
                    if line.strip():
                        errors.append(json.loads(line))

            if errors:
                lines.append("### ⚠️ Errors Captured\n")
                for err in errors[-5:]:
                    lines.append(f"- **{err.get('exception_type', 'Error')}**: {err.get('message', 'Unknown')[:100]}")
                lines.append("")
        except Exception as e:
            pass

    # Footer
    lines.append("---")
    lines.append("*Generated by Fortuna Race Pipeline*")

    # Output
    print("\n".join(lines))


if __name__ == "__main__":
    main()
