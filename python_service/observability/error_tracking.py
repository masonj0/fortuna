"""
Error tracking and reporting with Sentry-like functionality.
"""

import os
import sys
import json
import hashlib
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict
import threading
import asyncio


@dataclass
class ErrorEvent:
    """Captured error event."""
    error_id: str
    exception_type: str
    message: str
    stacktrace: str
    timestamp: datetime
    tags: Dict[str, str] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
    fingerprint: str = ""

    def __post_init__(self):
        if not self.fingerprint:
            # Generate fingerprint from exception type and first stack frame
            content = f"{self.exception_type}:{self.stacktrace.split(chr(10))[0] if self.stacktrace else ''}"
            self.fingerprint = hashlib.md5(content.encode()).hexdigest()[:12]


class ErrorTracker:
    """
    Tracks and aggregates errors with deduplication.
    Can export to file or external services.
    """

    def __init__(
        self,
        max_events: int = 1000,
        export_path: Optional[Path] = None,
        dsn: Optional[str] = None,  # For external service integration
    ):
        self.max_events = max_events
        self.export_path = export_path or Path("errors.json")
        self.dsn = dsn or os.environ.get('SENTRY_DSN')

        self._events: List[ErrorEvent] = []
        self._fingerprint_counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()
        self._hooks: List[Callable[[ErrorEvent], None]] = []

        # Context for tagging
        self._global_tags: Dict[str, str] = {}
        self._global_extra: Dict[str, Any] = {}

    def set_tag(self, key: str, value: str):
        """Set a global tag for all events."""
        self._global_tags[key] = value

    def set_extra(self, key: str, value: Any):
        """Set global extra data for all events."""
        self._global_extra[key] = value

    def add_hook(self, hook: Callable[[ErrorEvent], None]):
        """Add a hook to be called for each error."""
        self._hooks.append(hook)

    def capture(
        self,
        exception: BaseException,
        tags: Optional[Dict[str, str]] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> ErrorEvent:
        """Capture an exception."""
        # Build error event
        event = ErrorEvent(
            error_id=hashlib.md5(
                f"{datetime.utcnow().isoformat()}{id(exception)}".encode()
            ).hexdigest()[:16],
            exception_type=type(exception).__name__,
            message=str(exception),
            stacktrace=traceback.format_exc(),
            timestamp=datetime.utcnow(),
            tags={**self._global_tags, **(tags or {})},
            extra={**self._global_extra, **(extra or {})},
        )

        with self._lock:
            # Update counts
            self._fingerprint_counts[event.fingerprint] += 1

            # Add event (with size limit)
            self._events.append(event)
            if len(self._events) > self.max_events:
                self._events = self._events[-self.max_events:]

        # Run hooks
        for hook in self._hooks:
            try:
                hook(event)
            except Exception:
                pass  # Don't let hooks break error tracking

        # Export if path configured
        if self.export_path:
            self._export_event(event)

        return event

    def _export_event(self, event: ErrorEvent):
        """Append event to export file."""
        try:
            with open(self.export_path, 'a') as f:
                f.write(json.dumps(asdict(event), default=str) + "\n")
        except Exception:
            pass

    def get_summary(self) -> Dict[str, Any]:
        """Get error summary statistics."""
        with self._lock:
            return {
                "total_events": len(self._events),
                "unique_errors": len(self._fingerprint_counts),
                "top_errors": sorted(
                    [
                        {"fingerprint": fp, "count": count}
                        for fp, count in self._fingerprint_counts.items()
                    ],
                    key=lambda x: x["count"],
                    reverse=True
                )[:10],
                "recent_errors": [
                    {
                        "type": e.exception_type,
                        "message": e.message[:200],
                        "timestamp": e.timestamp.isoformat(),
                        "tags": e.tags,
                    }
                    for e in self._events[-10:]
                ],
            }

    def get_events_by_tag(self, tag: str, value: str) -> List[ErrorEvent]:
        """Get events matching a specific tag."""
        with self._lock:
            return [e for e in self._events if e.tags.get(tag) == value]


# Global error tracker instance
_error_tracker = ErrorTracker()


def capture_exception(
    exception: Optional[BaseException] = None,
    tags: Optional[Dict[str, str]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[ErrorEvent]:
    """
    Capture an exception to the global tracker.

    If no exception is provided, captures the current exception from sys.exc_info().
    """
    if exception is None:
        exc_info = sys.exc_info()
        if exc_info[1] is None:
            return None
        exception = exc_info[1]

    return _error_tracker.capture(exception, tags=tags, extra=extra)


def get_error_tracker() -> ErrorTracker:
    """Get the global error tracker instance."""
    return _error_tracker
