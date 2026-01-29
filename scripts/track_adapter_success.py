#!/usr/bin/env python3
"""
Adapter Success Tracker

Tracks successful adapter fetches in real-time and saves a spotlight summary
that persists even if the main reporter crashes.

This runs as a wrapper/monitor for the reporter and captures HTTP 200 responses
with race counts per track, saving them immediately to a fail-safe artifact.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict


class AdapterSuccessTracker:
    """
    Tracks adapter successes in real-time and saves spotlight summaries.

    This tracker:
    - Monitors adapter HTTP responses
    - Captures 200 status codes immediately
    - Aggregates race counts by track
    - Saves to a fail-safe artifact file
    - Persists data even if reporter crashes
    """

    def __init__(self, output_file: str = "adapter_success_spotlight.json"):
        self.output_file = Path(output_file)
        self.successes = defaultdict(lambda: {
            "adapter_name": "",
            "status_code": 0,
            "tracks": {},
            "total_races": 0,
            "fetch_time": "",
            "response_time_ms": 0
        })
        self.summary = {
            "generated_at": datetime.now().isoformat(),
            "total_successful_adapters": 0,
            "total_tracks": 0,
            "total_races": 0,
            "adapters": []
        }

    def record_success(
        self,
        adapter_name: str,
        status_code: int,
        tracks_with_races: Dict[str, int],
        response_time_ms: float = 0
    ):
        """
        Record a successful adapter fetch.

        Args:
            adapter_name: Name of the adapter
            status_code: HTTP status code (should be 200)
            tracks_with_races: Dict mapping track names to race counts
            response_time_ms: Response time in milliseconds
        """
        if status_code != 200:
            return  # Only track 200 responses

        total_races = sum(tracks_with_races.values())

        self.successes[adapter_name] = {
            "adapter_name": adapter_name,
            "status_code": status_code,
            "tracks": tracks_with_races,
            "total_races": total_races,
            "fetch_time": datetime.now().isoformat(),
            "response_time_ms": round(response_time_ms, 2)
        }

        # Save immediately
        self._save()

    def _save(self):
        """Save the current state to disk immediately."""
        # Update summary
        self.summary["generated_at"] = datetime.now().isoformat()
        self.summary["total_successful_adapters"] = len(self.successes)

        all_tracks = set()
        total_races = 0

        adapters_list = []
        for adapter_data in self.successes.values():
            adapters_list.append(adapter_data)
            all_tracks.update(adapter_data["tracks"].keys())
            total_races += adapter_data["total_races"]

        self.summary["total_tracks"] = len(all_tracks)
        self.summary["total_races"] = total_races
        self.summary["adapters"] = sorted(
            adapters_list,
            key=lambda x: x["total_races"],
            reverse=True
        )

        # Write to file atomically
        tmp_file = self.output_file.with_suffix('.tmp')
        with open(tmp_file, 'w') as f:
            json.dump(self.summary, f, indent=2)
        tmp_file.replace(self.output_file)

    def load_from_adapter_stats(self, stats_file: str = "adapter_stats.json"):
        """
        Load success data from adapter_stats.json if it exists.

        This allows us to capture data that was already collected by adapters.
        """
        stats_path = Path(stats_file)
        if not stats_path.exists():
            return

        try:
            with open(stats_path) as f:
                stats = json.load(f)

            # Use the new list format for adapter_stats.json
            if isinstance(stats, list):
                for adapter_data in stats:
                    adapter_name = adapter_data.get("adapter_name")
                    races_found = adapter_data.get("last_race_count", 0)
                    status = adapter_data.get("status")

                    # Celebrate ANY adapter that isn't completely disabled or open circuit
                    # "OK" and "DEGRADED" are both valid successes in "Simply Success" mode
                    if status in ["OK", "DEGRADED"]:
                        # --- SIMPLY SUCCESS SPOTLIGHT ---
                        # Celebrate HTTP 200 successes even with 0 races
                        self.record_success(
                            adapter_name=adapter_name,
                            status_code=200,
                            tracks_with_races={"Multiple Tracks": races_found},
                            response_time_ms=adapter_data.get("last_duration_s", 0) * 1000
                        )
            # Support legacy dict format
            elif isinstance(stats, dict):
                for adapter_name, adapter_data in stats.items():
                    if isinstance(adapter_data, dict):
                        races_found = adapter_data.get("races_found", 0)
                        successful = adapter_data.get("successful_requests", 0)

                        if successful > 0:
                            self.record_success(
                                adapter_name=adapter_name,
                                status_code=200,
                                tracks_with_races={"Unknown Tracks": races_found},
                                response_time_ms=0
                            )

        except Exception as e:
            print(f"Warning: Could not load adapter_stats.json: {e}")

    def load_from_raw_data(self, raw_data_file: str = "raw_race_data.json"):
        """
        Load success data from raw_race_data.json if it exists.

        This gives us detailed track-level information.
        """
        raw_path = Path(raw_data_file)
        if not raw_path.exists():
            return

        try:
            with open(raw_path) as f:
                raw_data = json.load(f)

            races = raw_data.get("races", [])

            # Group by adapter and track
            adapter_tracks = defaultdict(lambda: defaultdict(int))

            for race in races:
                source = race.get("source", "Unknown")
                venue = race.get("venue", "Unknown Venue")
                adapter_tracks[source][venue] += 1

            # Record each adapter's success
            for adapter_name, tracks in adapter_tracks.items():
                self.record_success(
                    adapter_name=adapter_name,
                    status_code=200,
                    tracks_with_races=dict(tracks),
                    response_time_ms=0
                )

        except Exception as e:
            print(f"Warning: Could not load raw_race_data.json: {e}")

    def generate_markdown_report(self) -> str:
        """Generate a markdown report of adapter successes."""
        if not self.summary["adapters"]:
            return "# Adapter Success Report\n\nNo successful adapters to report.\n"

        md = "# 🎯 Adapter Success Spotlight\n\n"
        md += f"**Generated:** {self.summary['generated_at']}\n\n"
        md += "## Summary\n\n"
        md += f"- ✅ **Successful Adapters:** {self.summary['total_successful_adapters']}\n"
        md += f"- 🏇 **Total Tracks:** {self.summary['total_tracks']}\n"
        md += f"- 🏁 **Total Races:** {self.summary['total_races']}\n\n"

        md += "## Detailed Results\n\n"

        for adapter_data in self.summary["adapters"]:
            adapter_name = adapter_data["adapter_name"]
            total_races = adapter_data["total_races"]
            tracks = adapter_data["tracks"]
            response_time = adapter_data["response_time_ms"]

            md += f"### ✅ {adapter_name}\n\n"
            md += f"- **Total Races:** {total_races}\n"
            md += f"- **Tracks:** {len(tracks)}\n"

            if response_time > 0:
                md += f"- **Response Time:** {response_time}ms\n"

            md += "\n**Races by Track:**\n\n"

            # Sort tracks by race count
            sorted_tracks = sorted(
                tracks.items(),
                key=lambda x: x[1],
                reverse=True
            )

            for track, count in sorted_tracks:
                md += f"- {track}: {count} races\n"

            md += "\n"

        return md


def main():
    """Main function to extract and save adapter successes."""
    tracker = AdapterSuccessTracker()

    print("🔍 Extracting adapter success data...")

    # Try to load from both adapter_stats and raw_data
    tracker.load_from_adapter_stats()
    tracker.load_from_raw_data()

    # Generate markdown report
    md_report = tracker.generate_markdown_report()

    with open("adapter_success_spotlight.md", "w") as f:
        f.write(md_report)

    # Print summary
    print(f"\n✅ Saved adapter success spotlight!")
    print(f"   - JSON: adapter_success_spotlight.json")
    print(f"   - Markdown: adapter_success_spotlight.md")
    print(f"\n📊 Summary:")
    print(f"   - Successful adapters: {tracker.summary['total_successful_adapters']}")
    print(f"   - Total tracks: {tracker.summary['total_tracks']}")
    print(f"   - Total races: {tracker.summary['total_races']}")

    if tracker.summary['adapters']:
        print(f"\n🏆 Top Performers:")
        for adapter_data in tracker.summary['adapters'][:3]:
            print(f"   - {adapter_data['adapter_name']}: "
                  f"{adapter_data['total_races']} races "
                  f"across {len(adapter_data['tracks'])} tracks")


if __name__ == "__main__":
    main()
