# python_service/adapters/mixins/debug_mixin.py
"""Mixin for debug HTML saving functionality."""

import os
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger(__name__)


class DebugMixin:
    """Mixin that provides debug HTML saving capabilities."""

    DEBUG_OUTPUT_DIR: str = "debug_output"

    def _save_debug_html(
        self,
        content: str,
        filename: str,
        *,
        enabled: bool = True,
        subdirectory: Optional[str] = None,
    ) -> Optional[Path]:
        """
        Save HTML content to a debug file for CI/debugging purposes.

        Args:
            content: The HTML content to save
            filename: Base filename (without extension)
            enabled: Whether debug saving is enabled
            subdirectory: Optional subdirectory within debug output dir

        Returns:
            Path to saved file, or None if saving failed/disabled
        """
        if not enabled:
            return None

        try:
            output_dir = Path(self.DEBUG_OUTPUT_DIR)
            if subdirectory:
                output_dir = output_dir / subdirectory
            output_dir.mkdir(parents=True, exist_ok=True)

            filepath = output_dir / f"{filename}.html"
            filepath.write_text(content, encoding="utf-8")
            log.debug("Saved debug HTML", path=str(filepath), size=len(content))
            return filepath
        except (OSError, IOError) as e:
            log.warning("Failed to save debug HTML", filename=filename, error=str(e))
            return None
