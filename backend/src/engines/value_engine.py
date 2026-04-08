"""
Value Bet detection engine.

Finds markets where one platform's price significantly diverges from the
cross-platform consensus. Unlike arbitrage (guaranteed profit), value bets
are +EV opportunities where you're betting the market is mispriced.

Example: If Polymarket says Trump at 18% but the consensus of Kalshi,
Metaculus, GJOpen, and Manifold says 25%, that's a value bet — buy YES
on Polymarket because the consensus thinks the true probability is higher.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re
import logging
from dataclasses import dataclass, field
from constants import PLATFORM_FEES

logger = logging.getLogger(__name__)

# Minimum edge (in absolute probability) to flag as a value bet
MIN_EDGE = 0.02  # 2 percentage points — lowered in Phase 3 for more signals
# Minimum number of platforms with data to compute consensus
MIN_PLATFORMS = 2
# Platforms where you can actually trade (others are reference only)
TRADEABLE_PLATFORMS = {"polymarket", "kalshi", "smarkets", "predictit", "sxbet", "opinion", "betfair", "matchbook"}
# All platforms count as sources for consensus computation
# The value bet is flagged on a TRADEABLE platform when it deviates from consensus


def _get_fee_info(source: str) -> dict:
    src = source.lower().strip()
    if src in PLATFORM_FEES:
        return PLATFORM_FEES[src]
    for name, fees in PLATFORM_FEES.items():
        if name in src:
            return fees
    return {"trade_fee": 0.01, "withdrawal_fee": 0.0, "profit_fee": 0.0}


@dataclass
class ValueBet:
    """A detected value betting opportunity."""
    event_name: str
    category: str
    platform: str
    platform_price: float
    consensus_price: float
    edge: float  # consensus - platform (positive = buy YES, negative = buy NO)
    direction: str  # "BUY YES" or "BUY NO"
    confidence: str
    num_sources: int
    sources: list
    market_url: str = ""
    volume: float = 0
    fees: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_name": self.event_name,
            "category": self.category,
            "platform": self.platform,
            "platform_price": self.platform_price,
            "consensus_price": self.consensus_price,
            "edge": self.edge,
            "direction": self.direction,
            "confidence": self.confidence,
            "num_sources": self.num_sources,
            "sources": self.sources,
            "market_url": self.market_url,
            "volume": self.volume,
            "fees": self.fees,
        }


def _normalize(text: str) -> str:
    """Normalize event name for grouping."""
    text = re.sub(r'\[.*?\]', '', text)
    text = text.replace(" -- ", " ")
    text = re.sub(r'^will\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\?+$', '', text)
    return text.strip().lower()


def _tokenize(text: str) -> set[str]:
    stop = {"will", "the", "a", "an", "in", "of", "to", "for", "by", "on", "at",
            "be", "is", "it", "and", "or", "not", "this", "that", "with", "from",
            "yes", "no", "market", "prediction", "2024", "2025", "2026", "2027", "2028"}
    tokens = set(re.findall(r'[a-z0-9]+', text.lower()))
    return tokens - stop


def detect_value_bets(market_prices: list) -> list[ValueBet]:
    """
    Detect value bets by comparing each tradeable platform's price
    against the cross-platform consensus.

    Strategy:
    1. Group similar events across platforms using token matching
    2. For each group, compute consensus probability (median of all sources)
    3. For tradeable platforms (Polymarket, Kalshi), check if their price
       diverges significantly from consensus
    4. Flag opportunities where |platform_price - consensus| > MIN_EDGE
    """
    from collections import defaultdict

    # Parse all prices
    parsed = []
    for price in market_prices:
        if isinstance(price, dict):
            event_name = price.get("event_name", "")
            source = price.get("source", "")
            prob = price.get("implied_probability", 0)
            market_url = price.get("market_url", "")
            volume = price.get("volume", 0) or 0
            category = price.get("category", "other")
        else:
            event_name = getattr(price, "event_name", "")
            source = getattr(price, "source", "")
            prob = getattr(price, "implied_probability", 0)
            market_url = getattr(price, "market_url", "")
            volume = getattr(price, "volume", 0) or 0
            category = getattr(price, "category", "other")

        if not event_name or not source or not prob:
            continue
        if prob <= 0.01 or prob >= 0.99:
            continue

        normalized = _normalize(event_name)
        tokens = _tokenize(normalized)
        if len(tokens) < 2:
            continue

        parsed.append({
            "event_name": event_name,
            "normalized": normalized,
            "tokens": tokens,
            "source": source.lower().strip(),
            "prob": prob,
            "market_url": market_url,
            "volume": volume,
            "category": category,
        })

    if len(parsed) < 2:
        return []

    # Try to use rapidfuzz for better matching
    try:
        from rapidfuzz import fuzz
        use_fuzzy = True
    except ImportError:
        use_fuzzy = False

    # Build groups of similar events
    # Use token inverted index for candidate pairs, then fuzzy match
    token_index = defaultdict(list)
    for i, p in enumerate(parsed):
        for token in p["tokens"]:
            token_index[token].append(i)

    # Find groups via connected components
    groups = defaultdict(set)  # group_id -> set of parsed indices
    assigned = {}  # parsed_idx -> group_id
    next_group = 0

    for token, indices in token_index.items():
        if len(indices) > 200:
            continue
        for i, idx_a in enumerate(indices):
            for idx_b in indices[i + 1:]:
                a = parsed[idx_a]
                b = parsed[idx_b]
                if a["source"] == b["source"]:
                    continue  # Same source, skip

                shared = a["tokens"] & b["tokens"]
                if len(shared) < 2:
                    continue

                # Quick similarity check
                if use_fuzzy:
                    score = fuzz.token_sort_ratio(a["normalized"], b["normalized"])
                    if score < 55:
                        continue
                else:
                    union = a["tokens"] | b["tokens"]
                    if len(shared) / len(union) < 0.4:
                        continue

                # These match — assign to same group
                ga = assigned.get(idx_a)
                gb = assigned.get(idx_b)
                if ga is None and gb is None:
                    assigned[idx_a] = next_group
                    assigned[idx_b] = next_group
                    groups[next_group] = {idx_a, idx_b}
                    next_group += 1
                elif ga is not None and gb is None:
                    assigned[idx_b] = ga
                    groups[ga].add(idx_b)
                elif ga is None and gb is not None:
                    assigned[idx_a] = gb
                    groups[gb].add(idx_a)
                elif ga != gb:
                    # Merge groups
                    for idx in groups[gb]:
                        assigned[idx] = ga
                    groups[ga].update(groups[gb])
                    del groups[gb]

    # For each group with 2+ sources, compute consensus and find value bets
    results = []
    seen = set()

    for group_id, indices in groups.items():
        members = [parsed[i] for i in indices]
        sources = set(m["source"] for m in members)

        if len(sources) < MIN_PLATFORMS:
            continue

        # Compute consensus (median probability across platforms)
        # Use one price per source (first seen)
        source_prices = {}
        for m in members:
            if m["source"] not in source_prices:
                source_prices[m["source"]] = m

        probs = sorted(sp["prob"] for sp in source_prices.values())
        consensus = probs[len(probs) // 2]  # median

        # Check each tradeable platform against consensus
        for src, sp in source_prices.items():
            base_src = src.replace("_mf", "")  # remove metaforecast suffix
            if base_src not in TRADEABLE_PLATFORMS:
                continue

            edge = consensus - sp["prob"]
            abs_edge = abs(edge)

            if abs_edge < MIN_EDGE:
                continue

            direction = "BUY YES" if edge > 0 else "BUY NO"

            # Dedup
            dedup_key = f"{base_src}:{sp['normalized'][:60]}"
            if dedup_key in seen:
                continue
            seen.add(dedup_key)

            # Confidence based on number of sources and edge size
            if len(sources) >= 4 and abs_edge >= 0.10:
                confidence = "high"
            elif len(sources) >= 3 and abs_edge >= 0.07:
                confidence = "medium"
            else:
                confidence = "low"

            source_details = [
                {"source": s, "prob": round(sp2["prob"], 3)}
                for s, sp2 in source_prices.items()
            ]

            results.append(ValueBet(
                event_name=sp["event_name"],
                category=sp["category"],
                platform=base_src,
                platform_price=round(sp["prob"], 4),
                consensus_price=round(consensus, 4),
                edge=round(edge, 4),
                direction=direction,
                confidence=confidence,
                num_sources=len(sources),
                sources=source_details,
                market_url=sp["market_url"],
                volume=sp["volume"],
                fees=_get_fee_info(base_src),
            ))

    results.sort(key=lambda x: abs(x.edge), reverse=True)
    return results[:50]
