"""
Generate GitHub Actions step summary with runtime insights.
"""

import json
from datetime import datetime
from pathlib import Path


def generate_summary():
    """Generate markdown summary for GitHub Actions."""
    lines = []
    lines.append("## 🐴 Fortuna Race Report Summary\n")

    # Basic info
    lines.append("### Run Information\n")
    lines.append(f"**Generated:** {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")

    # Race results
    if Path("qualified_races.json").exists():
        with open("qualified_races.json") as f:
            data = json.load(f)

        races = data.get("races", [])
        lines.append(f"\n### 📊 Results\n")
        lines.append(f"- **Qualified Races:** {len(races)}")
        lines.append(f"- **Analyzer:** {data.get('analyzer', 'unknown')}")

        # Venues breakdown
        venues = {}
        for race in races:
            venue = race.get("venue", "Unknown")
            venues[venue] = venues.get(venue, 0) + 1

        if venues:
            lines.append(f"\n#### Races by Venue\n")
            lines.append("| Venue | Races |")
            lines.append("|-------|-------|")
            for venue, count in sorted(venues.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"| {venue} | {count} |")

    # Metrics
    if Path("metrics.json").exists():
        with open("metrics.json") as f:
            metrics = json.load(f)

        lines.append(f"\n### 📈 Metrics\n")
        lines.append(f"- **Uptime:** {metrics.get('uptime_seconds', 0):.1f}s")

        if "histograms" in metrics:
            for name, hist in metrics["histograms"].items():
                if "fetch" in name.lower():
                    lines.append(f"- **{name}:** avg {hist.get('avg', 0):.2f}s")

    # Browser stats
    if Path("browser_selector_state.json").exists():
        with open("browser_selector_state.json") as f:
            browser_stats = json.load(f)

        lines.append(f"\n### 🌐 Browser Performance\n")
        lines.append("| Backend | Success Rate | Attempts |")
        lines.append("|---------|--------------|----------|")

        for backend, stats in browser_stats.get("stats", {}).items():
            total = stats.get("total_attempts", 0)
            success = stats.get("successful_attempts", 0)
            rate = f"{success/total:.1%}" if total > 0 else "N/A"
            lines.append(f"| {backend} | {rate} | {total} |")

    # Anomalies
    if Path("errors.json").exists():
        try:
            with open("errors.json") as f:
                errors = [json.loads(line) for line in f if line.strip()]

            if errors:
                lines.append(f"\n### ⚠️ Issues Detected\n")
                for error in errors[-5:]:
                    lines.append(f"- **{error.get('exception_type')}:** {error.get('message', '')[:100]}")
        except:
            pass

    # Data freshness warning
    lines.append(f"\n### 📅 Data Freshness\n")

    # Check adapter last success times from browser state
    if Path("browser_selector_state.json").exists():
        with open("browser_selector_state.json") as f:
            state = json.load(f)

        for backend, stats in state.get("stats", {}).items():
            last_success = stats.get("last_success")
            if last_success:
                try:
                    last_dt = datetime.fromisoformat(last_success)
                    age_minutes = (datetime.utcnow() - last_dt).total_seconds() / 60

                    if age_minutes > 60:
                        lines.append(f"⚠️ **{backend}** data may be stale (last success: {age_minutes:.0f}m ago)")
                except:
                    pass

    lines.append("\n---")
    lines.append("*Report generated automatically by Fortuna Race Pipeline*")

    print("\n".join(lines))


if __name__ == "__main__":
    generate_summary()
