"""
Structured logging with contextual metadata.
"""

import logging
import json
import sys
import os
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar
from functools import wraps

# Context variables for request-scoped metadata
_log_context: ContextVar[Dict[str, Any]] = ContextVar('log_context', default={})


class StructuredFormatter(logging.Formatter):
    """JSON formatter with contextual metadata."""

    def __init__(self, include_trace: bool = True):
        super().__init__()
        self.include_trace = include_trace
        self.hostname = os.environ.get('HOSTNAME', 'unknown')
        self.service = os.environ.get('SERVICE_NAME', 'race-pipeline')

    def format(self, record: logging.LogRecord) -> str:
        # Base log entry
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service,
            "hostname": self.hostname,
        }

        # Add source location
        log_entry["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add context from ContextVar
        context = _log_context.get()
        if context:
            log_entry["context"] = context

        # Add extra fields from record
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)

        # Add exception info
        if record.exc_info and self.include_trace:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_entry, default=str)


class ContextualLogger(logging.LoggerAdapter):
    """Logger adapter that includes contextual metadata."""

    def process(self, msg, kwargs):
        # Merge context
        extra = kwargs.get('extra', {})
        extra_fields = {}

        # Add adapter-specific fields
        for key in list(kwargs.keys()):
            if key not in ('exc_info', 'stack_info', 'stacklevel', 'extra'):
                extra_fields[key] = kwargs.pop(key)

        if extra_fields:
            extra['extra_fields'] = extra_fields

        kwargs['extra'] = extra
        return msg, kwargs

    def bind(self, **kwargs) -> 'ContextualLogger':
        """Create a child logger with additional context."""
        new_extra = {**self.extra, **kwargs}
        return ContextualLogger(self.logger, new_extra)


def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
    include_trace: bool = True
) -> None:
    """Configure structured logging for the application."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    if json_output:
        handler.setFormatter(StructuredFormatter(include_trace=include_trace))
    else:
        handler.setFormatter(logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
        ))

    root_logger.addHandler(handler)

    # Reduce noise from libraries
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('playwright').setLevel(logging.WARNING)


def get_logger(name: str, **initial_context) -> ContextualLogger:
    """Get a contextual logger instance."""
    logger = logging.getLogger(name)
    return ContextualLogger(logger, initial_context)


def with_context(**context):
    """Decorator to add logging context for the duration of a function."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            token = _log_context.set({**_log_context.get(), **context})
            try:
                return await func(*args, **kwargs)
            finally:
                _log_context.reset(token)

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            token = _log_context.set({**_log_context.get(), **context})
            try:
                return func(*args, **kwargs)
            finally:
                _log_context.reset(token)

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    return decorator


import asyncio  # Required for the decorator
