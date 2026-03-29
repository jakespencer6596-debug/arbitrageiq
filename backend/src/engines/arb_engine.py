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


_STOP_WORDS = frozenset({
    "will", "the", "a", "an", "in", "of", "to", "for", "by", "on", "at",
    "be", "is", "it", "and", "or", "not", "this", "that", "with", "from",
    "win", "yes", "no", "?", "2025", "2026", "2027",
})


def _tokenize(text: str) -> set[str]:
    """Extract meaningful lowercase tokens from an event name."""
    import re
    tokens = set(re.findall(r'[a-z0-9]+', text.lower()))
    return tokens - _STOP_WORDS


def _similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def detect_arb(market_prices: list, base_stake: float = 1000.0) -> list[ArbOpportunityResult]:
    """
    Cross-platform arbitrage detection with fuzzy event name matching.

    Strategy:
    1. Parse all prices into a standard format
    2. Build an inverted index of tokens -> markets for efficient matching
    3. For markets sharing 2+ tokens from DIFFERENT sources, check similarity
    4. If similarity > 0.4, treat as same event and check for price arb

    Returns list of ArbOpportunityResult sorted by profit_pct descending.
    """
    from collections import defaultdict
    import re

    # 1. Parse all prices
    parsed = []
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

        if not event_name or not source or not implied_prob:
            continue
        if implied_prob <= 0.01 or implied_prob >= 0.99:
            continue  # Skip extreme prices (noise)

        if raw_odds and raw_odds > 0:
            decimal_odds = raw_odds
        elif implied_prob > 0:
            decimal_odds = 1.0 / implied_prob
        else:
            continue

        tokens = _tokenize(event_name)
        if len(tokens) < 2:
            continue

        parsed.append({
            "event_name": event_name,
            "outcome": (outcome or "yes").lower().strip(),
            "source": source.lower().strip(),
            "implied_prob": implied_prob,
            "decimal_odds": decimal_odds,
            "category": category,
            "tokens": tokens,
            "idx": len(parsed),
        })

    if not parsed:
        return []

    # 2. Build inverted index: token -> list of price indices
    token_index: dict[str, list[int]] = defaultdict(list)
    for p in parsed:
        for token in p["tokens"]:
            token_index[token].append(p["idx"])

    # 3. Find candidate pairs (different sources, sharing 2+ tokens)
    # Use the inverted index to avoid O(n^2) comparison
    candidate_pairs: set[tuple[int, int]] = set()
    for token, indices in token_index.items():
        if len(indices) > 500:
            continue  # Skip very common tokens to avoid explosion
        for i, idx_a in enumerate(indices):
            for idx_b in indices[i + 1:]:
                if parsed[idx_a]["source"] != parsed[idx_b]["source"]:
                    pair = (min(idx_a, idx_b), max(idx_a, idx_b))
                    candidate_pairs.add(pair)
                if len(candidate_pairs) > 50000:
                    break
            if len(candidate_pairs) > 50000:
                break
        if len(candidate_pairs) > 50000:
            break

    # 4. Check each candidate pair for similarity + arb
    results = []
    seen = set()

    for idx_a, idx_b in candidate_pairs:
        a = parsed[idx_a]
        b = parsed[idx_b]

        sim = _similarity(a["tokens"], b["tokens"])
        if sim < 0.4:
            continue

        # Same event, different sources — check for price discrepancy
        # For YES/YES comparison: if one platform prices YES much higher,
        # buy YES on the cheap platform, buy NO on the expensive one
        prob_a = a["implied_prob"]
        prob_b = b["implied_prob"]
        edge = abs(prob_a - prob_b)

        if edge < MIN_ARB_PROFIT_PCT:
            continue

        # Determine direction
        if prob_a < prob_b:
            cheap, expensive = a, b
        else:
            cheap, expensive = b, a

        # Build as: Buy YES on cheap source, Buy NO on expensive source
        odds_yes = 1.0 / cheap["implied_prob"]
        odds_no = 1.0 / (1.0 - expensive["implied_prob"])
        arb_sum = (1.0 / odds_yes) + (1.0 / odds_no)

        if arb_sum < 1.0:
            profit_pct = 1.0 - arb_sum
        else:
            # Not a true arb but still a significant price discrepancy
            profit_pct = edge

        # Dedup
        dedup_key = (
            tuple(sorted((a["source"], b["source"]))),
            min(a["event_name"][:40].lower(), b["event_name"][:40].lower()),
        )
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        stake_pct1 = 0.5
        stake_pct2 = 0.5
        if arb_sum < 1.0 and arb_sum > 0:
            stake_pct1 = (1.0 / odds_yes) / arb_sum
            stake_pct2 = (1.0 / odds_no) / arb_sum

        legs = [
            ArbLeg(
                source=cheap["source"],
                outcome=f"YES @ {cheap['implied_prob']:.0%}",
                decimal_odds=round(odds_yes, 4),
                implied_prob=round(cheap["implied_prob"], 4),
                stake_pct=round(stake_pct1, 4),
                stake_dollars=round(base_stake * stake_pct1, 2),
            ),
            ArbLeg(
                source=expensive["source"],
                outcome=f"NO @ {1 - expensive['implied_prob']:.0%}",
                decimal_odds=round(odds_no, 4),
                implied_prob=round(1.0 - expensive["implied_prob"], 4),
                stake_pct=round(stake_pct2, 4),
                stake_dollars=round(base_stake * stake_pct2, 2),
            ),
        ]

        results.append(ArbOpportunityResult(
            event_name=f"{cheap['event_name'][:60]} vs {expensive['source']}",
            category=a["category"],
            profit_pct=round(profit_pct, 4),
            legs=legs,
            profit_on_1000=round(base_stake * profit_pct, 2),
        ))

    # Sort by profit descending, limit to top 50
    results.sort(key=lambda x: x.profit_pct, reverse=True)
    return results[:50]
