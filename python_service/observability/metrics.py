"""
Prometheus-style metrics collection for race pipeline.
"""

import time
import json
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from pathlib import Path
import threading


@dataclass
class MetricPoint:
    """A single metric data point."""
    name: str
    value: float
    timestamp: datetime
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: str = "gauge"  # gauge, counter, histogram


@dataclass
class HistogramBucket:
    """Histogram bucket for latency tracking."""
    le: float  # Less than or equal
    count: int = 0


class MetricsCollector:
    """
    Collects and exports Prometheus-style metrics.
    Thread-safe and async-compatible.
    """

    # Default histogram buckets (in seconds)
    DEFAULT_BUCKETS = [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, float('inf')]

    def __init__(self, export_path: Optional[Path] = None):
        self._counters: Dict[str, float] = defaultdict(float)
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, Dict[str, Any]] = {}
        self._labels: Dict[str, Dict[str, str]] = {}
        self._lock = threading.Lock()
        self._export_path = export_path or Path("metrics.json")
        self._start_time = datetime.utcnow()

    def _make_key(self, name: str, labels: Dict[str, str]) -> str:
        """Create a unique key for metric + labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    # Counter methods
    def inc(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None):
        """Increment a counter."""
        labels = labels or {}
        key = self._make_key(name, labels)
        with self._lock:
            self._counters[key] += value
            self._labels[key] = labels

    def counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current counter value."""
        key = self._make_key(name, labels or {})
        return self._counters.get(key, 0.0)

    # Gauge methods
    def set(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge value."""
        labels = labels or {}
        key = self._make_key(name, labels)
        with self._lock:
            self._gauges[key] = value
            self._labels[key] = labels

    def gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get current gauge value."""
        key = self._make_key(name, labels or {})
        return self._gauges.get(key, 0.0)

    # Histogram methods
    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Record an observation in a histogram."""
        labels = labels or {}
        key = self._make_key(name, labels)

        with self._lock:
            if key not in self._histograms:
                self._histograms[key] = {
                    "buckets": {b: 0 for b in self.DEFAULT_BUCKETS},
                    "sum": 0.0,
                    "count": 0,
                }
                self._labels[key] = labels

            hist = self._histograms[key]
            hist["sum"] += value
            hist["count"] += 1

            for bucket in self.DEFAULT_BUCKETS:
                if value <= bucket:
                    hist["buckets"][bucket] += 1

    def timer(self, name: str, labels: Optional[Dict[str, str]] = None):
        """Context manager for timing operations."""
        return MetricTimer(self, name, labels)

    # Reporting
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics as a dictionary."""
        with self._lock:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {
                        "buckets": {str(b): c for b, c in v["buckets"].items()},
                        "sum": v["sum"],
                        "count": v["count"],
                        "avg": v["sum"] / v["count"] if v["count"] > 0 else 0,
                    }
                    for k, v in self._histograms.items()
                },
            }

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []

        with self._lock:
            # Export counters
            for key, value in self._counters.items():
                lines.append(f"{key} {value}")

            # Export gauges
            for key, value in self._gauges.items():
                lines.append(f"{key} {value}")

            # Export histograms
            for key, hist in self._histograms.items():
                base_name = key.split("{")[0]
                labels_part = key[len(base_name):] if "{" in key else ""

                for bucket, count in hist["buckets"].items():
                    bucket_labels = f'le="{bucket}"'
                    if labels_part:
                        full_labels = labels_part[:-1] + "," + bucket_labels + "}"
                    else:
                        full_labels = "{" + bucket_labels + "}"
                    lines.append(f"{base_name}_bucket{full_labels} {count}")

                lines.append(f"{base_name}_sum{labels_part} {hist['sum']}")
                lines.append(f"{base_name}_count{labels_part} {hist['count']}")

        return "\n".join(lines)

    def export_json(self, path: Optional[Path] = None):
        """Export metrics to JSON file."""
        path = path or self._export_path
        with open(path, 'w') as f:
            json.dump(self.get_all_metrics(), f, indent=2, default=str)

    def reset(self):
        """Reset all metrics."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._labels.clear()


class MetricTimer:
    """Context manager for timing operations."""

    def __init__(self, collector: MetricsCollector, name: str, labels: Optional[Dict[str, str]] = None):
        self.collector = collector
        self.name = name
        self.labels = labels
        self.start_time = None

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.perf_counter() - self.start_time
        self.collector.observe(self.name, elapsed, self.labels)

        # Also track success/failure
        status = "error" if exc_type else "success"
        self.collector.inc(
            f"{self.name}_total",
            labels={**(self.labels or {}), "status": status}
        )

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)


# Global metrics instance
metrics = MetricsCollector()


# Convenience decorators
def timed(name: str, labels: Optional[Dict[str, str]] = None):
    """Decorator to time function execution."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            async with metrics.timer(name, labels):
                return await func(*args, **kwargs)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with metrics.timer(name, labels):
                return func(*args, **kwargs)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


from functools import wraps
