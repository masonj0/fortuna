"""
Anomaly detection for race data quality assurance.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from collections import defaultdict
import statistics

from ..observability import get_logger, metrics, capture_exception

logger = get_logger(__name__)


@dataclass
class HistoricalStats:
    """Historical statistics for a track/source."""
    samples: List[float] = field(default_factory=list)
    max_samples: int = 100

    def add(self, value: float):
        self.samples.append(value)
        if len(self.samples) > self.max_samples:
            self.samples = self.samples[-self.max_samples:]

    @property
    def mean(self) -> float:
        return statistics.mean(self.samples) if self.samples else 0.0

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.samples) if len(self.samples) >= 2 else 0.0

    @property
    def count(self) -> int:
        return len(self.samples)


@dataclass
class Anomaly:
    """Detected anomaly in race data."""
    anomaly_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    context: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class AnomalyDetector:
    """
    Detects anomalies in race data based on historical patterns.
    """

    # Thresholds
    MIN_SAMPLES_FOR_DETECTION = 5
    Z_SCORE_THRESHOLD = 2.5  # Standard deviations from mean

    # Expected ranges
    EXPECTED_RUNNERS_RANGE = (2, 20)
    EXPECTED_ODDS_RANGE = (1.01, 500.0)
    MAX_SCRATCHES_RATIO = 0.5  # More than 50% scratched is suspicious

    def __init__(self, history_path: Optional[Path] = None):
        self.history_path = history_path or Path("anomaly_history.json")

        # Historical stats by track/source
        self._race_counts: Dict[str, HistoricalStats] = defaultdict(HistoricalStats)
        self._runner_counts: Dict[str, HistoricalStats] = defaultdict(HistoricalStats)
        self._odds_ranges: Dict[str, HistoricalStats] = defaultdict(HistoricalStats)

        self._load_history()

    def _load_history(self):
        """Load historical stats from file."""
        try:
            if self.history_path.exists():
                with open(self.history_path) as f:
                    data = json.load(f)

                for key, samples in data.get("race_counts", {}).items():
                    self._race_counts[key].samples = samples
                for key, samples in data.get("runner_counts", {}).items():
                    self._runner_counts[key].samples = samples

                logger.info("Loaded anomaly detection history")
        except Exception as e:
            logger.warning(f"Failed to load anomaly history: {e}")

    def _save_history(self):
        """Save historical stats to file."""
        try:
            data = {
                "updated_at": datetime.utcnow().isoformat(),
                "race_counts": {k: v.samples for k, v in self._race_counts.items()},
                "runner_counts": {k: v.samples for k, v in self._runner_counts.items()},
            }
            with open(self.history_path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"Failed to save anomaly history: {e}")

    def analyze_races(
        self,
        races: List[Any],
        source: str,
    ) -> Tuple[List[Anomaly], Dict[str, Any]]:
        """
        Analyze a set of races for anomalies.

        Args:
            races: List of Race objects
            source: Source adapter name

        Returns:
            Tuple of (anomalies_found, analysis_stats)
        """
        anomalies = []
        stats = {
            "total_races": len(races),
            "total_runners": 0,
            "scratched_runners": 0,
            "venues": set(),
        }

        # Aggregate stats
        runners_per_race = []
        for race in races:
            runner_count = len(race.runners) if hasattr(race, 'runners') else 0
            scratched = sum(1 for r in race.runners if r.scratched) if hasattr(race, 'runners') else 0

            runners_per_race.append(runner_count)
            stats["total_runners"] += runner_count
            stats["scratched_runners"] += scratched
            stats["venues"].add(race.venue if hasattr(race, 'venue') else 'unknown')

            # Per-race anomaly checks
            race_anomalies = self._check_race_anomalies(race, source)
            anomalies.extend(race_anomalies)

        stats["venues"] = list(stats["venues"])

        # Aggregate anomaly checks
        aggregate_anomalies = self._check_aggregate_anomalies(
            races, source, runners_per_race, stats
        )
        anomalies.extend(aggregate_anomalies)

        # Update historical data
        key = source
        self._race_counts[key].add(len(races))
        if runners_per_race:
            avg_runners = statistics.mean(runners_per_race)
            self._runner_counts[key].add(avg_runners)

        self._save_history()

        # Emit metrics
        for anomaly in anomalies:
            metrics.inc("anomalies_detected", labels={
                "type": anomaly.anomaly_type,
                "severity": anomaly.severity,
                "source": source
            })

        return anomalies, stats

    def _check_race_anomalies(self, race, source: str) -> List[Anomaly]:
        """Check a single race for anomalies."""
        anomalies = []

        if not hasattr(race, 'runners'):
            return anomalies

        runner_count = len(race.runners)
        active_runners = [r for r in race.runners if not r.scratched]
        scratched_ratio = 1 - (len(active_runners) / runner_count) if runner_count > 0 else 0

        # Zero runners
        if runner_count == 0:
            anomalies.append(Anomaly(
                anomaly_type="zero_runners",
                severity="high",
                message=f"Race {race.venue} R{race.race_number} has zero runners",
                context={"race_id": race.id, "venue": race.venue}
            ))

        # Too few active runners
        elif len(active_runners) < self.EXPECTED_RUNNERS_RANGE[0]:
            anomalies.append(Anomaly(
                anomaly_type="low_runner_count",
                severity="medium",
                message=f"Race has only {len(active_runners)} active runners",
                context={"race_id": race.id, "active_runners": len(active_runners)}
            ))

        # Too many scratches
        if scratched_ratio > self.MAX_SCRATCHES_RATIO and runner_count > 3:
            anomalies.append(Anomaly(
                anomaly_type="high_scratch_rate",
                severity="medium",
                message=f"High scratch rate: {scratched_ratio:.0%}",
                context={
                    "race_id": race.id,
                    "scratched": runner_count - len(active_runners),
                    "total": runner_count
                }
            ))

        # Check odds
        for runner in active_runners:
            if hasattr(runner, 'odds') and runner.odds:
                for odds_source, odds_data in runner.odds.items():
                    win_odds = odds_data.win if hasattr(odds_data, 'win') else None
                    if win_odds:
                        if win_odds < self.EXPECTED_ODDS_RANGE[0]:
                            anomalies.append(Anomaly(
                                anomaly_type="invalid_odds",
                                severity="low",
                                message=f"Odds too low: {win_odds}",
                                context={"runner": runner.name, "odds": win_odds}
                            ))
                        elif win_odds > self.EXPECTED_ODDS_RANGE[1]:
                            anomalies.append(Anomaly(
                                anomaly_type="extreme_odds",
                                severity="low",
                                message=f"Extremely high odds: {win_odds}",
                                context={"runner": runner.name, "odds": win_odds}
                            ))

        return anomalies

    def _check_aggregate_anomalies(
        self,
        races: List,
        source: str,
        runners_per_race: List[int],
        stats: Dict
    ) -> List[Anomaly]:
        """Check for anomalies in aggregate data."""
        anomalies = []
        key = source

        # Compare race count to historical
        race_stats = self._race_counts.get(key)
        if race_stats and race_stats.count >= self.MIN_SAMPLES_FOR_DETECTION:
            z_score = self._calculate_z_score(len(races), race_stats)

            if z_score < -self.Z_SCORE_THRESHOLD:
                anomalies.append(Anomaly(
                    anomaly_type="low_race_count",
                    severity="high",
                    message=f"Unusually low race count: {len(races)} (avg: {race_stats.mean:.1f})",
                    context={
                        "current": len(races),
                        "average": race_stats.mean,
                        "z_score": z_score
                    }
                ))
            elif z_score > self.Z_SCORE_THRESHOLD:
                anomalies.append(Anomaly(
                    anomaly_type="high_race_count",
                    severity="low",
                    message=f"Unusually high race count: {len(races)} (avg: {race_stats.mean:.1f})",
                    context={
                        "current": len(races),
                        "average": race_stats.mean,
                        "z_score": z_score
                    }
                ))

        # Zero races when we usually have some
        if len(races) == 0 and race_stats and race_stats.mean > 0:
            anomalies.append(Anomaly(
                anomaly_type="no_races",
                severity="critical",
                message=f"Zero races returned from {source} (historical avg: {race_stats.mean:.1f})",
                context={"source": source, "historical_avg": race_stats.mean}
            ))

        return anomalies

    def _calculate_z_score(self, value: float, stats: HistoricalStats) -> float:
        """Calculate z-score for a value given historical stats."""
        if stats.stdev == 0:
            return 0.0
        return (value - stats.mean) / stats.stdev

    def get_thresholds_for_source(self, source: str) -> Dict[str, Any]:
        """Get current thresholds based on historical data."""
        key = source
        race_stats = self._race_counts.get(key, HistoricalStats())
        runner_stats = self._runner_counts.get(key, HistoricalStats())

        return {
            "race_count": {
                "mean": race_stats.mean,
                "stdev": race_stats.stdev,
                "samples": race_stats.count,
                "min_expected": max(0, race_stats.mean - 2 * race_stats.stdev),
                "max_expected": race_stats.mean + 2 * race_stats.stdev,
            },
            "runners_per_race": {
                "mean": runner_stats.mean,
                "stdev": runner_stats.stdev,
                "samples": runner_stats.count,
            }
        }
