#!/usr/bin/env python
"""
Fortuna Unified Race Reporter

Generates HTML, JSON, and Markdown summary reports for GitHub Actions
by directly invoking the OddsEngine and AnalyzerEngine without a live API.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

# Ensure the project root is in the path to allow for direct imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from web_service.backend.engine import OddsEngine
from web_service.backend.analyzer import AnalyzerEngine
from web_service.backend.config import get_settings
from web_service.backend.models import Race


class LogLevel(Enum):
    """Log level enumeration with emoji support."""
    INFO = ("INFO", "ℹ️")
    SUCCESS = ("SUCCESS", "✅")
    ERROR = ("ERROR", "❌")
    WARNING = ("WARNING", "⚠️")
    DEBUG = ("DEBUG", "🔍")

    @property
    def emoji(self) -> str:
        return self.value[1]


@dataclass
class ReporterConfig:
    """Configuration for the race reporter."""
    template_path: Path = field(default_factory=lambda: Path("scripts/templates/race_report_template.html"))
    html_output_path: Path = field(default_factory=lambda: Path("race-report.html"))
    json_output_path: Path = field(default_factory=lambda: Path("qualified_races.json"))
    markdown_summary_path: Path = field(default_factory=lambda: Path("github_summary.md"))
    raw_json_output_path: Path = field(default_factory=lambda: Path("raw_race_data.json"))

    max_retries: int = field(default_factory=lambda: int(os.getenv("MAX_RETRIES", "3")))
    request_timeout: int = field(default_factory=lambda: int(os.getenv("REQUEST_TIMEOUT", "30")))
    analyzer_type: str = field(default_factory=lambda: os.getenv("ANALYZER_TYPE", "tiny_field_trifecta"))
    force_refresh: bool = field(default_factory=lambda: os.getenv("FORCE_REFRESH", "false").lower() == "true")
    max_summary_races: int = 25

    # All known adapters for exclusion logic
    ALL_ADAPTERS: tuple[str, ...] = (
        "AtTheRacesAdapter", "BetfairAdapter", "BetfairGreyhoundAdapter",
        "BrisnetAdapter", "EquibaseAdapter", "FanDuelAdapter", "GbgbApiAdapter",
        "GreyhoundAdapter", "HarnessAdapter", "HorseRacingNationAdapter",
        "NYRABetsAdapter", "OddscheckerAdapter", "PuntersAdapter",
        "RacingAndSportsAdapter", "RacingAndSportsGreyhoundAdapter",
        "RacingPostAdapter", "RacingTVAdapter", "SportingLifeAdapter",
        "TabAdapter", "TheRacingApiAdapter", "TimeformAdapter",
        "TwinSpiresAdapter", "TVGAdapter", "XpressbetAdapter",
        "PointsBetGreyhoundAdapter",
    )

    # Reliable adapters that don't require API keys.
    # Timeform, Equibase, and Brisnet are temporarily disabled due to persistent,
    # unrecoverable errors (e.g., Incapsula blocking, 500 errors).
    RELIABLE_NON_KEYED_ADAPTERS: tuple[str, ...] = (
        "AtTheRacesAdapter", "SportingLifeAdapter", "RacingPostAdapter", "OddscheckerAdapter",
    )

    @property
    def excluded_adapters(self) -> list[str]:
        """Calculate which adapters to exclude."""
        return [a for a in self.ALL_ADAPTERS if a not in self.RELIABLE_NON_KEYED_ADAPTERS]


@dataclass
class ReportMetrics:
    """Metrics collected during report generation."""
    total_races_fetched: int = 0
    qualified_races: int = 0
    adapters_used: list[str] = field(default_factory=list)
    adapters_failed: list[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    end_time: datetime | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_races_fetched": self.total_races_fetched,
            "qualified_races": self.qualified_races,
            "adapters_used": self.adapters_used,
            "adapters_failed": self.adapters_failed,
            "duration_seconds": self.duration_seconds,
            "errors": self.errors,
            "timestamp": self.start_time.isoformat(),
        }


class Reporter:
    """Main reporter class for generating race reports."""

    def __init__(self, config: ReporterConfig | None = None):
        self.config = config or ReporterConfig()
        self.metrics = ReportMetrics()

    def log(self, message: str, level: LogLevel = LogLevel.INFO) -> None:
        """Print a timestamped log message."""
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {level.emoji} {message}", flush=True)

        if level == LogLevel.ERROR:
            self.metrics.errors.append(message)

    def generate_html_report(self, race_data: dict[str, Any]) -> bool:
        """Generates the HTML report from a template."""
        self.log("Generating HTML report...")

        try:
            if not self.config.template_path.exists():
                self.log(f"Template not found at {self.config.template_path}", LogLevel.ERROR)
                return self._generate_fallback_html(race_data)

            template = self.config.template_path.read_text(encoding="utf-8")

            # Inject data and metrics
            race_data_with_metrics = {
                **race_data,
                "generation_metrics": self.metrics.to_dict(),
            }

            report_html = template.replace(
                "__RACE_DATA_PLACEHOLDER__",
                json.dumps(race_data_with_metrics, default=str)
            )

            self.config.html_output_path.write_text(report_html, encoding="utf-8")
            self.log(f"Generated HTML report at {self.config.html_output_path}", LogLevel.SUCCESS)
            return True

        except Exception as e:
            self.log(f"Failed to generate HTML report: {e}", LogLevel.ERROR)
            return self._generate_fallback_html(race_data)

    def _generate_fallback_html(self, race_data: dict[str, Any]) -> bool:
        """Generate a minimal fallback HTML report if template fails."""
        self.log("Generating fallback HTML report...", LogLevel.WARNING)

        try:
            races = race_data.get("races", [])
            html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Fortuna Race Report (Fallback)</title>
    <style>
        body {{ font-family: system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 1rem; }}
        .race {{ border: 1px solid #ccc; padding: 1rem; margin: 1rem 0; border-radius: 8px; }}
        .error {{ color: #c00; background: #fee; padding: 1rem; border-radius: 4px; }}
    </style>
</head>
<body>
    <h1>🐴 Fortuna Race Report</h1>
    <p class="error">⚠️ This is a fallback report. The main template could not be loaded.</p>
    <p>Found {len(races)} qualified race(s)</p>
    <pre>{json.dumps(race_data, indent=2, default=str)}</pre>
</body>
</html>"""
            self.config.html_output_path.write_text(html, encoding="utf-8")
            return True
        except Exception as e:
            self.log(f"Failed to generate fallback HTML: {e}", LogLevel.ERROR)
            return False

    def generate_markdown_summary(self, races: list[Race]) -> bool:
        """Generates a Markdown summary for the GitHub Actions UI."""
        self.log("Generating Markdown summary...")

        try:
            lines = [
                "# 🐴 Fortuna Race Report",
                "",
                f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
                f"**Analyzer:** `{self.config.analyzer_type}`",
                f"**Duration:** {self.metrics.duration_seconds:.1f}s",
                "",
            ]

            if self.metrics.errors:
                lines.extend([
                    "### ⚠️ Warnings",
                    "",
                    *[f"- {e}" for e in self.metrics.errors[:5]],
                    "",
                ])

            if not races:
                lines.append("### 🔭 No races found matching filters.")
            else:
                lines.extend([
                    f"### ⚡ Found {len(races)} Qualified Race(s)",
                    "",
                    "| Score | Time | Venue | Race | Runners |",
                    "|:-----:|:-----|:------|:----:|:-------:|",
                ])

                for race in races[:self.config.max_summary_races]:
                    start_time = race.start_time
                    if isinstance(start_time, str):
                        try:
                            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                        except ValueError:
                            start_time = None

                    time_str = start_time.strftime('%H:%M') if start_time else "N/A"
                    score = f"{race.qualification_score:.1f}" if race.qualification_score is not None else "N/A"
                    venue = race.venue or "Unknown"
                    race_num = race.race_number or "?"
                    runners = len(race.runners) if race.runners else 0

                    lines.append(f"| {score} | {time_str} | **{venue}** | {race_num} | {runners} |")

                if len(races) > self.config.max_summary_races:
                    lines.append(f"\n*...and {len(races) - self.config.max_summary_races} more races*")

            lines.extend([
                "",
                "---",
                "",
                "<details>",
                "<summary>📊 Generation Metrics</summary>",
                "",
                f"- Total races fetched: {self.metrics.total_races_fetched}",
                f"- Qualified races: {self.metrics.qualified_races}",
                f"- Adapters used: {len(self.metrics.adapters_used)}",
                f"- Adapters failed: {len(self.metrics.adapters_failed)}",
                "",
                "</details>",
            ])

            self.config.markdown_summary_path.write_text("\n".join(lines), encoding="utf-8")
            self.log(f"Generated Markdown summary at {self.config.markdown_summary_path}", LogLevel.SUCCESS)
            return True

        except Exception as e:
            self.log(f"Failed to write Markdown summary: {e}", LogLevel.ERROR)
            return False

    def save_json(self, data: dict[str, Any], path: Path, description: str) -> bool:
        """Save JSON data with error handling."""
        try:
            path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            self.log(f"Saved {description} to {path}", LogLevel.SUCCESS)
            return True
        except Exception as e:
            self.log(f"Failed to save {description}: {e}", LogLevel.ERROR)
            return False

    async def fetch_with_retry(
        self,
        odds_engine: OddsEngine,
        date_str: str,
    ) -> dict[str, Any]:
        """Fetch race data with retry logic."""
        last_error = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                self.log(f"Fetching race data (attempt {attempt}/{self.config.max_retries})...")
                data = await asyncio.wait_for(
                    odds_engine.fetch_all_odds(date_str),
                    timeout=self.config.request_timeout * 2
                )
                return data
            except asyncio.TimeoutError:
                last_error = "Request timed out"
                self.log(f"Attempt {attempt} timed out", LogLevel.WARNING)
            except Exception as e:
                last_error = str(e)
                self.log(f"Attempt {attempt} failed: {e}", LogLevel.WARNING)

            if attempt < self.config.max_retries:
                wait_time = 2 ** attempt  # Exponential backoff
                self.log(f"Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

        raise RuntimeError(f"All {self.config.max_retries} fetch attempts failed. Last error: {last_error}")

    async def run(self) -> bool:
        """Main entry point for the reporter."""
        self.log("=== Fortuna Unified Race Reporter ===")
        self.log(f"Analyzer: {self.config.analyzer_type}")
        self.log(f"Excluding {len(self.config.excluded_adapters)} adapters")

        settings = get_settings()
        odds_engine = OddsEngine(config=settings, exclude_adapters=self.config.excluded_adapters)
        analyzer_engine = AnalyzerEngine()

        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        success = True

        try:
            # Fetch data with retries
            aggregated_data = await self.fetch_with_retry(odds_engine, today_str)

            # Save raw data
            self.save_json(aggregated_data, self.config.raw_json_output_path, "raw race data")

            all_races_raw = aggregated_data.get("races", [])
            self.metrics.total_races_fetched = len(all_races_raw)

            if not all_races_raw:
                self.log("No races returned from OddsEngine. This is a critical failure.", LogLevel.ERROR)
                success = False
                all_races = []
            else:
                # Validate races with error tolerance
                all_races = []
                for i, race_data in enumerate(all_races_raw):
                    try:
                        all_races.append(Race(**race_data))
                    except Exception as e:
                        self.log(f"Failed to validate race {i}: {e}", LogLevel.WARNING)

                self.log(f"Validated {len(all_races)}/{len(all_races_raw)} races")

            # Analyze races
            self.log(f"Analyzing with '{self.config.analyzer_type}' analyzer...")

            try:
                analyzer = analyzer_engine.get_analyzer(self.config.analyzer_type)
                result = analyzer.qualify_races(all_races)
            except Exception as e:
                self.log(f"Analyzer failed: {e}", LogLevel.ERROR)
                result = {"races": [], "criteria": {}}

            qualified_races = result.get("races", [])
            criteria = result.get("criteria", {})
            self.metrics.qualified_races = len(qualified_races)

            self.log(f"Found {len(qualified_races)} qualified races", LogLevel.SUCCESS)

            # Prepare report data
            report_data = {
                "races": [r.model_dump(mode='json') for r in qualified_races],
                "analysis_metadata": criteria,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "analyzer": self.config.analyzer_type,
            }

            # Generate all outputs
            self.save_json(report_data, self.config.json_output_path, "qualified races JSON")
            self.generate_html_report(report_data)
            self.generate_markdown_summary(qualified_races)

        except Exception as e:
            self.log(f"Critical error: {e}", LogLevel.ERROR)
            import traceback
            traceback.print_exc()
            success = False

        finally:
            self.metrics.end_time = datetime.now(timezone.utc)
            await odds_engine.close()
            self.log(f"Reporter finished in {self.metrics.duration_seconds:.1f}s")

        return success


async def main() -> int:
    """CLI entry point."""
    reporter = Reporter()
    success = await reporter.run()
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
