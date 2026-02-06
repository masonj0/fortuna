"""Odds parsing utilities with comprehensive format support."""

import re
from typing import Optional, Any
from decimal import Decimal, InvalidOperation


MIN_VALID_ODDS = 1.01
MAX_VALID_ODDS = 1000.0


def parse_odds_to_decimal(odds_str: str) -> Optional[float]:
    """
    Parse various odds formats to decimal odds.

    Supports:
    - Fractional: "5/2", "9-2", "5-1"
    - Decimal: "3.50", "3,50" (European)
    - American: "+250", "-150"
    - Even/Evens: "EVN", "EVEN", "evs"
    - Morning line: "5-2 ML"

    Returns:
        Decimal odds as float, or None if unparseable
    """
    if not odds_str:
        return None

    # Clean input
    odds_str = odds_str.strip().upper()

    # Remove common suffixes
    odds_str = re.sub(r'\s*(ML|MTP|AM|PM)$', '', odds_str)

    # Handle even money
    if odds_str in ('EVN', 'EVEN', 'EVS', 'EVENS'):
        return 2.0

    # Handle scratched/invalid
    if odds_str in ('SCR', 'SCRATCHED', '--', 'N/A', ''):
        return None

    try:
        # Try fractional odds (5/2 or 5-2)
        frac_match = re.match(r'^(\d+)[/\-](\d+)$', odds_str)
        if frac_match:
            num = int(frac_match.group(1))
            den = int(frac_match.group(2))
            if den > 0:
                return round((num / den) + 1.0, 2)

        # Try American odds (+250 or -150)
        american_match = re.match(r'^([+-])(\d+)$', odds_str)
        if american_match:
            sign = american_match.group(1)
            value = int(american_match.group(2))
            if sign == '+':
                return round((value / 100) + 1.0, 2)
            else:
                return round((100 / value) + 1.0, 2)

        # Try decimal odds (already in correct format)
        decimal_str = odds_str.replace(',', '.')
        decimal_match = re.match(r'^(\d+\.?\d*)$', decimal_str)
        if decimal_match:
            value = float(decimal_match.group(1))
            if MIN_VALID_ODDS <= value < MAX_VALID_ODDS:
                return round(value, 2)

    except (ValueError, ZeroDivisionError, InvalidOperation):
        pass

    return None


class SmartOddsExtractor:
    """
    Advanced heuristics for extracting odds from noisy HTML or text.
    Scans for various patterns and returns the first plausible odds found.
    """
    @staticmethod
    def extract_from_text(text: str) -> Optional[float]:
        if not text:
            return None
        # Try to find common odds patterns in the text
        # 1. Decimal odds (e.g. 5.00, 10.5)
        decimals = re.findall(r"(\d+\.\d+)", text)
        for d in decimals:
            val = float(d)
            if MIN_VALID_ODDS <= val < MAX_VALID_ODDS:
                return round(val, 2)

        # 2. Fractional odds (e.g. 7/4, 10-1)
        fractions = re.findall(r"(\d+)\s*[/\-]\s*(\d+)", text)
        for num, den in fractions:
            n, d = int(num), int(den)
            if d > 0 and (n / d) > 0.1:
                return round((n / d) + 1.0, 2)

        return None

    @staticmethod
    def extract_from_node(node: Any) -> Optional[float]:
        """Scans a selectolax node for odds using multiple strategies."""
        # Strategy 1: Look at text content of the entire node
        if hasattr(node, 'text'):
            if val := SmartOddsExtractor.extract_from_text(node.text()):
                return val

        # Strategy 2: Look at attributes
        if hasattr(node, 'attributes'):
            for attr in ["data-odds", "data-price", "data-bestprice", "title"]:
                if val_str := node.attributes.get(attr):
                    if val := parse_odds_to_decimal(val_str):
                        return val

        return None


def format_odds_display(decimal_odds: float, style: str = 'fractional') -> str:
    """
    Format decimal odds for display.

    Args:
        decimal_odds: Odds in decimal format
        style: 'fractional', 'american', or 'decimal'

    Returns:
        Formatted odds string
    """
    if not decimal_odds or decimal_odds < 1.01:
        return "N/A"

    if style == 'decimal':
        return f"{decimal_odds:.2f}"

    elif style == 'american':
        if decimal_odds >= 2.0:
            american = int((decimal_odds - 1) * 100)
            return f"+{american}"
        else:
            american = int(-100 / (decimal_odds - 1))
            return str(american)

    else:  # fractional
        # Common fractional odds lookup
        profit = decimal_odds - 1

        # Check common fractions
        common_fractions = [
            (0.5, "1/2"), (1.0, "1/1"), (1.5, "3/2"), (2.0, "2/1"),
            (2.5, "5/2"), (3.0, "3/1"), (4.0, "4/1"), (5.0, "5/1"),
            (6.0, "6/1"), (8.0, "8/1"), (10.0, "10/1"), (12.0, "12/1"),
            (14.0, "14/1"), (16.0, "16/1"), (20.0, "20/1"), (25.0, "25/1"),
            (33.0, "33/1"), (50.0, "50/1"), (100.0, "100/1"),
        ]

        for value, display in common_fractions:
            if abs(profit - value) < 0.05:
                return display

        # Approximate to nearest reasonable fraction
        if profit < 1:
            return f"{int(profit * 2)}/2"
        else:
            return f"{int(profit)}/1"
