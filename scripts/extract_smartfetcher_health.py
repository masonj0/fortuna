#!/usr/bin/env python3
"""
Extracts SmartFetcher health metrics from logs and adapter stats.
"""

import json
from pathlib import Path
from collections import defaultdict

def main():
    health_summary = {
        "engines_used": [],
        "adapters_by_engine": defaultdict(list),
        "total_requests": 0
    }

    # Extract engines used from the engine_health.log (created by grep in workflow)
    log_path = Path("engine_health.log")
    engines = set()
    if log_path.exists():
        content = log_path.read_text()
        for engine_name in ["playwright", "camoufox", "httpx"]:
            if engine_name in content.lower():
                engines.add(engine_name)

    health_summary["engines_used"] = sorted(list(engines))

    # Read adapter stats to populate more info if possible
    stats_path = Path("adapter_stats.json")
    if stats_path.exists():
        try:
            with open(stats_path) as f:
                stats = json.load(f)
            # Future enhancement: extract engine from stats if fortuna_reporter is updated
        except:
            pass

    with open("smartfetcher_health.json", "w") as f:
        json.dump(health_summary, f, indent=2, default=list)

    print("✅ SmartFetcher health summary generated")

if __name__ == "__main__":
    main()
