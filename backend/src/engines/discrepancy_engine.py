"""
Discrepancy detection engine.
Compares prediction market prices against public data sources
to find markets that appear mispriced relative to available evidence.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import logging
from dataclasses import dataclass
from typing import Optional
from constants import THRESHOLDS

logger = logging.getLogger(__name__)


@dataclass
class DiscrepancyResult:
    """A detected discrepancy between market and public data."""
    market_id: str
    source: str
    event_name: str
    category: str
    market_probability: float
    data_implied_probability: float
    edge_pct: float
    direction: str
    data_source: str
    data_value: float
    data_unit: str
    confidence: str
    notes: str = ""

    def to_dict(self) -> dict:
        """Serialize for JSON/DB storage."""
        return {
            "market_id": self.market_id,
            "source": self.source,
            "event_name": self.event_name,
            "category": self.category,
            "market_probability": self.market_probability,
            "data_implied_probability": self.data_implied_probability,
            "edge_pct": self.edge_pct,
            "direction": self.direction,
            "data_source": self.data_source,
            "data_value": self.data_value,
            "data_unit": self.data_unit,
            "confidence": self.confidence,
            "notes": self.notes,
        }


def detect_discrepancy(
    market: dict,
    public_data: dict,
    category: str
) -> Optional[DiscrepancyResult]:
    """
    Compare a prediction market's implied probability against
    what public data suggests.

    Args:
        market: Dict with keys: market_id, source, event_name, implied_probability
        public_data: Dict with keys: derived_probability, value, unit, source, confidence
        category: Market category for threshold selection

    Returns:
        DiscrepancyResult if edge exceeds threshold, else None
    """
    threshold = THRESHOLDS.get(category, 0.10)

    market_prob = market.get("implied_probability", 0)
    data_prob = public_data.get("derived_probability", 0)

    if not market_prob or not data_prob:
        return None

    edge = abs(market_prob - data_prob)

    if edge < threshold:
        return None

    direction = "BUY_YES" if data_prob > market_prob else "BUY_NO"

    confidence = public_data.get("confidence", "medium")
    if public_data.get("data_age_hours", 0) > 24:
        confidence = "low"
    if public_data.get("historical_std", 0) > 5 and category == "weather":
        confidence = "low" if confidence == "medium" else confidence

    return DiscrepancyResult(
        market_id=market.get("market_id", ""),
        source=market.get("source", ""),
        event_name=market.get("event_name", ""),
        category=category,
        market_probability=round(market_prob, 3),
        data_implied_probability=round(data_prob, 3),
        edge_pct=round(edge, 3),
        direction=direction,
        data_source=public_data.get("source", ""),
        data_value=public_data.get("value", 0),
        data_unit=public_data.get("unit", ""),
        confidence=confidence,
        notes=public_data.get("notes", ""),
    )
