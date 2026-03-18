"""
Arbitrage detection engine.
Scans all current market prices for guaranteed-profit opportunities
across sportsbooks and prediction markets.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from dataclasses import dataclass
from constants import MIN_ARB_PROFIT_PCT


@dataclass
class ArbLeg:
    """One leg of an arbitrage bet."""
    source: str
    outcome: str
    decimal_odds: float
    implied_prob: float
    stake_pct: float
    stake_dollars: float


@dataclass
class ArbOpportunityResult:
    """A detected arbitrage opportunity."""
    event_name: str
    category: str
    profit_pct: float
    legs: list
    profit_on_1000: float
    is_live: bool = False

    def to_dict(self) -> dict:
        """Serialize for JSON/DB storage."""
        return {
            "event_name": self.event_name,
            "category": self.category,
            "profit_pct": self.profit_pct,
            "legs": [
                {
                    "source": leg.source,
                    "outcome": leg.outcome,
                    "decimal_odds": leg.decimal_odds,
                    "implied_prob": leg.implied_prob,
                    "stake_pct": leg.stake_pct,
                    "stake_dollars": leg.stake_dollars,
                }
                for leg in self.legs
            ],
            "profit_on_1000": self.profit_on_1000,
        }


def american_to_decimal(american: float) -> float:
    """Convert American odds to decimal. +150 -> 2.50, -110 -> 1.909."""
    if american > 0:
        return (american / 100) + 1
    else:
        return (100 / abs(american)) + 1


def decimal_to_implied(decimal_odds: float) -> float:
    """Convert decimal odds to raw implied probability."""
    if decimal_odds <= 0:
        return 0.0
    return 1.0 / decimal_odds


def strip_vig_multiplicative(implied_probs: list[float]) -> list[float]:
    """
    Remove vig using multiplicative method.
    Works for 2-outcome and multi-outcome markets.
    """
    total = sum(implied_probs)
    if total == 0:
        return implied_probs
    return [p / total for p in implied_probs]


def detect_arb(market_prices: list, base_stake: float = 1000.0) -> list[ArbOpportunityResult]:
    """
    Main arbitrage detection function.

    Expects MarketPrice rows or dicts with: source, event_name, outcome,
    implied_probability, raw_odds, category.

    Returns list of ArbOpportunityResult sorted by profit_pct descending.
    """
    events = {}
    for price in market_prices:
        if isinstance(price, dict):
            event_name = price.get("event_name", "")
            outcome = price.get("outcome", "")
            source = price.get("source", "")
            implied_prob = price.get("implied_probability", 0)
            raw_odds = price.get("raw_odds")
            category = price.get("category", "other")
        else:
            event_name = getattr(price, "event_name", "")
            outcome = getattr(price, "outcome", "")
            source = getattr(price, "source", "")
            implied_prob = getattr(price, "implied_probability", 0)
            raw_odds = getattr(price, "raw_odds", None)
            category = getattr(price, "category", "other")

        if not event_name or not outcome or not implied_prob:
            continue

        key = event_name.lower().strip()
        if key not in events:
            events[key] = {"name": event_name, "category": category, "outcomes": {}}

        outcome_key = outcome.lower().strip()
        if outcome_key not in events[key]["outcomes"]:
            events[key]["outcomes"][outcome_key] = []

        if raw_odds and raw_odds > 0:
            decimal_odds = raw_odds
        elif implied_prob > 0:
            decimal_odds = 1.0 / implied_prob
        else:
            continue

        events[key]["outcomes"][outcome_key].append({
            "source": source,
            "decimal_odds": decimal_odds,
            "implied_prob": implied_prob,
        })

    results = []
    for event_key, event in events.items():
        outcomes = event["outcomes"]
        if len(outcomes) < 2:
            continue

        best_per_outcome = {}
        for outcome, offers in outcomes.items():
            best = max(offers, key=lambda x: x["decimal_odds"])
            best_per_outcome[outcome] = best

        arb_sum = sum(1.0 / b["decimal_odds"] for b in best_per_outcome.values())

        if arb_sum < 1.0:
            profit_pct = 1.0 - arb_sum
            if profit_pct < MIN_ARB_PROFIT_PCT:
                continue

            legs = []
            for outcome, best in best_per_outcome.items():
                stake_pct = (1.0 / best["decimal_odds"]) / arb_sum
                stake_dollars = base_stake * stake_pct
                legs.append(ArbLeg(
                    source=best["source"],
                    outcome=outcome,
                    decimal_odds=round(best["decimal_odds"], 4),
                    implied_prob=round(best["implied_prob"], 4),
                    stake_pct=round(stake_pct, 4),
                    stake_dollars=round(stake_dollars, 2),
                ))

            results.append(ArbOpportunityResult(
                event_name=event["name"],
                category=event["category"],
                profit_pct=round(profit_pct, 4),
                legs=legs,
                profit_on_1000=round(base_stake * profit_pct, 2),
            ))

    return sorted(results, key=lambda x: x.profit_pct, reverse=True)
