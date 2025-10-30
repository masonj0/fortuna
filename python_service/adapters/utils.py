# python_service/adapters/utils.py
# Compatibility shim to re-export parse_odds from the centralized location.

from ..utils.odds import parse_odds

__all__ = ["parse_odds"]
