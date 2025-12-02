"""Backend service module for Fortuna Faucet."""
from pathlib import Path

# Explicitly mark this as a proper package
__package__ = "web_service.backend"
__all__ = ["main", "api"]

# Package metadata
PACKAGE_ROOT = Path(__file__).parent
