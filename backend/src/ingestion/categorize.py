"""
Shared market categorization for all ingestion modules.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from constants import KEYWORD_MAP


def categorise(title: str) -> str:
    """
    Map a market title to an ArbitrageIQ category using keyword matching.

    Lowercases the title and checks every keyword in KEYWORD_MAP.
    First match wins.  Defaults to 'other'.
    """
    lower = title.lower() if title else ""
    for keyword, category in KEYWORD_MAP.items():
        if keyword in lower:
            return category
    return "other"
