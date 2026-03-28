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

    Real arbitrage = same outcome priced differently across DIFFERENT platforms.
    We group prices by (event_name, outcome), find the best odds per source,
    and check every cross-source pair for an arb (1/odds1 + 1/odds2 < 1.0).

    Expects MarketPrice rows or dicts with: source, event_name, outcome,
    implied_probability, raw_odds, category.

    Returns list of ArbOpportunityResult sorted by profit_pct descending.
    """
    from collections import defaultdict
    from itertools import combinations

    # Group prices by (event_name, outcome) — each entry keeps per-source best
    groups: dict[tuple[str, str], dict] = {}

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

        if not event_name or not outcome or not implied_prob or not source:
            continue

        if raw_odds and raw_odds > 0:
            decimal_odds = raw_odds
        elif implied_prob > 0:
            decimal_odds = 1.0 / implied_prob
        else:
            continue

        key = (event_name.lower().strip(), outcome.lower().strip())
        if key not in groups:
            groups[key] = {
                "name": event_name,
                "outcome": outcome,
                "category": category,
                "by_source": {},
            }

        # Keep the best (highest) decimal odds per source
        src_key = source.lower().strip()
        existing = groups[key]["by_source"].get(src_key)
        if existing is None or decimal_odds > existing["decimal_odds"]:
            groups[key]["by_source"][src_key] = {
                "source": source,
                "decimal_odds": decimal_odds,
                "implied_prob": implied_prob,
            }

    # Now look for cross-source arbs within each (event, outcome) group.
    # An arb on the same outcome across two sources means:
    #   - Buy YES on source A at odds1 and sell YES (buy NO) on source B at odds2
    #   - Arb condition: 1/odds_yes_A + 1/odds_no_B < 1.0
    # But since we group by outcome, we need complementary outcomes.
    #
    # Regroup by event_name so we can pair complementary outcomes across sources.
    events: dict[str, dict] = {}
    for (event_key, outcome_key), group in groups.items():
        if event_key not in events:
            events[event_key] = {"name": group["name"], "category": group["category"], "outcomes": {}}
        events[event_key]["outcomes"][outcome_key] = group["by_source"]

    results = []
    for event_key, event in events.items():
        outcomes = event["outcomes"]
        if len(outcomes) < 2:
            continue

        # For each pair of complementary outcomes (e.g. "yes"/"no"),
        # find cross-source arb: best odds on outcome1 from source A +
        # best odds on outcome2 from source B, where A != B.
        outcome_keys = list(outcomes.keys())
        for i, oc1 in enumerate(outcome_keys):
            for oc2 in outcome_keys[i + 1:]:
                sources1 = outcomes[oc1]  # dict: source -> {decimal_odds, ...}
                sources2 = outcomes[oc2]  # dict: source -> {decimal_odds, ...}

                # Try every pair where the two legs come from different sources
                for src1, offer1 in sources1.items():
                    for src2, offer2 in sources2.items():
                        if src1 == src2:
                            continue

                        odds1 = offer1["decimal_odds"]
                        odds2 = offer2["decimal_odds"]
                        arb_sum = (1.0 / odds1) + (1.0 / odds2)

                        if arb_sum < 1.0:
                            profit_pct = 1.0 - arb_sum
                            if profit_pct < MIN_ARB_PROFIT_PCT:
                                continue

                            stake_pct1 = (1.0 / odds1) / arb_sum
                            stake_pct2 = (1.0 / odds2) / arb_sum

                            legs = [
                                ArbLeg(
                                    source=offer1["source"],
                                    outcome=oc1,
                                    decimal_odds=round(odds1, 4),
                                    implied_prob=round(offer1["implied_prob"], 4),
                                    stake_pct=round(stake_pct1, 4),
                                    stake_dollars=round(base_stake * stake_pct1, 2),
                                ),
                                ArbLeg(
                                    source=offer2["source"],
                                    outcome=oc2,
                                    decimal_odds=round(odds2, 4),
                                    implied_prob=round(offer2["implied_prob"], 4),
                                    stake_pct=round(stake_pct2, 4),
                                    stake_dollars=round(base_stake * stake_pct2, 2),
                                ),
                            ]

                            results.append(ArbOpportunityResult(
                                event_name=event["name"],
                                category=event["category"],
                                profit_pct=round(profit_pct, 4),
                                legs=legs,
                                profit_on_1000=round(base_stake * profit_pct, 2),
                            ))

    # Deduplicate: keep the best arb per (event, outcome pair, source pair)
    seen = set()
    deduped = []
    for r in sorted(results, key=lambda x: x.profit_pct, reverse=True):
        leg_sources = tuple(sorted((r.legs[0].source, r.legs[1].source)))
        leg_outcomes = tuple(sorted((r.legs[0].outcome, r.legs[1].outcome)))
        dedup_key = (r.event_name.lower().strip(), leg_outcomes, leg_sources)
        if dedup_key not in seen:
            seen.add(dedup_key)
            deduped.append(r)

    return deduped
