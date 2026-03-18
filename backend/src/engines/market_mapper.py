"""
Market mapper — auto-discovery brain.
When a new market appears on Kalshi or Polymarket, this module
determines which public data sources can provide a ground-truth comparison.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re
from constants import KEYWORD_MAP, FRED_SERIES


def map_market(market: dict) -> dict:
    """
    Takes a raw market dict and returns a mapping result.

    Args:
        market: Dict with event_name, and optionally series_ticker or metadata

    Returns:
        {
            "category": str,
            "data_sources": list[str],
            "is_mapped": bool,
            "confidence": str,
        }
    """
    event_name = ""
    if isinstance(market, dict):
        event_name = market.get("event_name", "").lower()
        series = market.get("series_ticker", "").lower()
    else:
        event_name = getattr(market, "event_name", "").lower()
        series = getattr(market, "metadata_", {}).get("series_ticker", "") if hasattr(market, "metadata_") else ""
        series = series.lower() if series else ""

    text = f"{event_name} {series}"

    # Score each category by keyword hits
    category_scores = {}
    for keyword, category in KEYWORD_MAP.items():
        if keyword in text:
            category_scores[category] = category_scores.get(category, 0) + 1

    if not category_scores:
        return {"category": "other", "data_sources": [], "is_mapped": False, "confidence": "low"}

    category = max(category_scores, key=category_scores.get)
    data_sources = []

    if category == "weather":
        data_sources.append("open_meteo")
        data_sources.append("nws_alerts")

    elif category == "economic":
        for series_id, info in FRED_SERIES.items():
            label_lower = info["label"].lower()
            if any(word in text for word in label_lower.split()):
                data_sources.append(f"fred_{series_id}")
        if not data_sources:
            data_sources.append("fred_SP500")

    elif category == "political":
        data_sources.append("predictit_cross")

    elif category == "sports":
        data_sources.append("odds_api_cross")

    confidence = "high" if category_scores.get(category, 0) >= 2 else "medium"

    return {
        "category": category,
        "data_sources": data_sources,
        "is_mapped": len(data_sources) > 0,
        "confidence": confidence,
    }
