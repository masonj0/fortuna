# python_service/adapters/utils/odds_validator.py
"""Utilities for validating and processing odds data."""

from datetime import datetime
from decimal import Decimal
from typing import Optional, Union

from ..constants import MAX_VALID_ODDS, MIN_VALID_ODDS
from ...models import OddsData


def is_valid_odds(odds: Union[float, Decimal, None]) -> bool:
    """
    Check if odds value is within valid range.

    Args:
        odds: The odds value to validate

    Returns:
        True if odds are valid, False otherwise
    """
    if odds is None:
        return False
    try:
        odds_float = float(odds)
        return MIN_VALID_ODDS <= odds_float < MAX_VALID_ODDS
    except (TypeError, ValueError):
        return False


def create_odds_data(
    source_name: str,
    win_odds: Union[float, Decimal, None],
    place_odds: Union[float, Decimal, None] = None,
) -> Optional[OddsData]:
    """
    Create an OddsData object if odds are valid.

    Args:
        source_name: Name of the odds source
        win_odds: Win odds value
        place_odds: Optional place odds value

    Returns:
        OddsData object or None if odds are invalid
    """
    if not is_valid_odds(win_odds):
        return None

    return OddsData(
        win=win_odds,
        place=place_odds if is_valid_odds(place_odds) else None,
        source=source_name,
        last_updated=datetime.now(),
    )
