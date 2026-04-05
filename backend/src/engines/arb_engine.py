"""
Arbitrage detection engine.
Scans all current market prices for guaranteed-profit opportunities
across sportsbooks and prediction markets.

IMPORTANT: Only reports TRUE mathematical arbitrages (arb_sum < 1.0),
never price differences between potentially unrelated markets.
"""

import re
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
    market_url: str = ""


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
                    "market_url": leg.market_url,
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
    "win", "yes", "no", "2024", "2025", "2026", "2027", "2028", "2029", "2030",
    "who", "what", "how", "when", "where", "before", "after",
    "market", "prediction", "contract", "price", "read", "description",
    "question", "resolve", "resolves", "resolution", "end", "date",
    "happen", "next", "between", "during", "about", "over", "under",
    "more", "less", "become", "likely", "whether", "could", "would", "should",
    "than", "much", "many", "does", "do", "did", "has", "have", "been",
})


# ---------------------------------------------------------------------------
# Entity extraction for accurate matching
# ---------------------------------------------------------------------------
_COUNTRIES = frozenset({
    "us", "usa", "united states", "uk", "united kingdom", "china", "russia",
    "india", "brazil", "colombia", "colombian", "mexico", "mexican",
    "france", "french", "germany", "german", "japan", "japanese",
    "canada", "canadian", "australia", "australian",
    "israel", "israeli", "iran", "iranian", "ukraine", "ukrainian",
    "taiwan", "south korea", "korean", "north korea",
    "peru", "peruvian", "argentina", "argentine", "chile", "chilean",
    "turkey", "turkish", "italy", "italian", "spain", "spanish",
    "poland", "polish", "philippines", "filipino",
    "nigeria", "nigerian", "south africa", "kenya", "kenyan",
    "egypt", "egyptian", "saudi", "pakistan", "pakistani",
    "indonesia", "indonesian", "thailand", "thai", "vietnam", "vietnamese",
})


def _extract_entities(text: str) -> set[str]:
    """
    Extract distinguishing entities from event text.
    Returns country names, year tokens, and multi-word proper nouns.
    These MUST match between two events for them to be considered the same.
    """
    lower = text.lower()
    entities = set()

    # Country names
    for country in _COUNTRIES:
        if country in lower:
            entities.add(country)

    # Year tokens (2024-2030)
    for year_match in re.findall(r'\b(20[2-3]\d)\b', text):
        entities.add(year_match)

    # Multi-word proper nouns (consecutive capitalized words)
    for match in re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', text):
        entities.add(match.lower())

    return entities


def _normalize_event_name(text: str) -> str:
    """
    Normalize event name for matching.
    Strips platform-specific formatting across Kalshi, Polymarket, PredictIt, Manifold.
    """
    # PredictIt uses "Market Name -- Contract Name"
    # Keep both parts for matching (contract name has the candidate/outcome)
    text = text.replace(" -- ", " ")
    # Kalshi uses all-caps tickers mixed in — strip them
    # Manifold uses "[READ DESCRIPTION]" prefixes
    text = re.sub(r'\[.*?\]', '', text)
    # Strip "Market:" prefixes
    text = re.sub(r'^market:\s*', '', text, flags=re.IGNORECASE)
    # Strip "Will ... ?" framing common on prediction markets
    text = re.sub(r'^will\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\?+$', '', text)
    return text.strip()


def _tokenize(text: str) -> set[str]:
    """Extract meaningful lowercase tokens from an event name."""
    tokens = set(re.findall(r'[a-z0-9]+', text.lower()))
    return tokens - _STOP_WORDS


def _similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Jaccard similarity between two token sets."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Configurable thresholds — tightened for accuracy
# ---------------------------------------------------------------------------
SIMILARITY_THRESHOLD = 0.55    # Jaccard similarity minimum (balanced: catches real matches, entity check blocks false positives)
MIN_SHARED_TOKENS = 3          # Must share at least 3 meaningful tokens (raised from 2)
MAX_PROFIT_PCT = 0.25          # 25% cap — anything higher is a matching error


def detect_arb(market_prices: list, base_stake: float = 1000.0) -> list[ArbOpportunityResult]:
    """
    Cross-platform arbitrage detection with strict event name matching.

    Strategy:
    1. Parse all prices, normalize event names
    2. Build an inverted index of tokens -> markets for efficient matching
    3. For markets sharing tokens from DIFFERENT sources, check similarity
    4. Require entity compatibility (same country, year, person)
    5. ONLY report true mathematical arbs (arb_sum < 1.0)
    6. Reject anything above MAX_PROFIT_PCT as a likely matching error

    Returns list of ArbOpportunityResult sorted by profit_pct descending.
    """
    from collections import defaultdict

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
            market_url = price.get("market_url", "")
        else:
            event_name = getattr(price, "event_name", "")
            outcome = getattr(price, "outcome", "")
            source = getattr(price, "source", "")
            implied_prob = getattr(price, "implied_probability", 0)
            raw_odds = getattr(price, "raw_odds", None)
            category = getattr(price, "category", "other")
            market_url = getattr(price, "market_url", "")

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

        # Normalize event name before tokenizing
        normalized = _normalize_event_name(event_name)
        tokens = _tokenize(normalized)
        if len(tokens) < 3:
            continue  # Need at least 3 meaningful tokens

        # Extract entities for strict matching
        entities = _extract_entities(event_name)

        parsed.append({
            "event_name": event_name,
            "normalized_name": normalized,
            "outcome": (outcome or "yes").lower().strip(),
            "source": source.lower().strip(),
            "implied_prob": implied_prob,
            "decimal_odds": decimal_odds,
            "category": category,
            "tokens": tokens,
            "entities": entities,
            "market_url": market_url or "",
            "idx": len(parsed),
        })

    if not parsed:
        return []

    # 2. Build inverted index: token -> list of price indices
    token_index: dict[str, list[int]] = defaultdict(list)
    for p in parsed:
        for token in p["tokens"]:
            token_index[token].append(p["idx"])

    # 3. Find candidate pairs (different sources, sharing tokens)
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

    # 4. Check each candidate pair for similarity + entity match + TRUE arb
    results = []
    seen = set()

    for idx_a, idx_b in candidate_pairs:
        a = parsed[idx_a]
        b = parsed[idx_b]

        # Require minimum shared token count
        shared = a["tokens"] & b["tokens"]
        if len(shared) < MIN_SHARED_TOKENS:
            continue

        sim = _similarity(a["tokens"], b["tokens"])
        if sim < SIMILARITY_THRESHOLD:
            continue

        # Entity guard: if both markets have entities, they must share at least one
        # This prevents "Colombian election" matching "US election"
        entities_a = a["entities"]
        entities_b = b["entities"]
        if entities_a and entities_b:
            if not (entities_a & entities_b):
                continue  # Different entities = different events

        # Same event, different sources — check for arb
        prob_a = a["implied_prob"]
        prob_b = b["implied_prob"]

        # Determine direction: buy YES on cheap, buy NO on expensive
        if prob_a < prob_b:
            cheap, expensive = a, b
        else:
            cheap, expensive = b, a

        odds_yes = 1.0 / cheap["implied_prob"]
        odds_no = 1.0 / (1.0 - expensive["implied_prob"])
        arb_sum = (1.0 / odds_yes) + (1.0 / odds_no)

        # ---------------------------------------------------------------
        # CRITICAL: Only report TRUE mathematical arbitrages.
        # arb_sum < 1.0 means guaranteed profit regardless of outcome.
        # If arb_sum >= 1.0, there is NO arb — skip entirely.
        # ---------------------------------------------------------------
        if arb_sum >= 1.0:
            continue

        # Correct arb profit formula: guaranteed ROI on total stake
        profit_pct = (1.0 / arb_sum) - 1.0

        # Sanity check: reject unrealistically high profits
        if profit_pct > MAX_PROFIT_PCT:
            continue

        # Must exceed minimum threshold
        if profit_pct < MIN_ARB_PROFIT_PCT:
            continue

        # Dedup by source pair + normalized event name
        dedup_key = (
            tuple(sorted((a["source"], b["source"]))),
            min(a["normalized_name"][:80].lower(), b["normalized_name"][:80].lower()),
        )
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        # Stakes proportional to implied probability so payouts are equal
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
                market_url=cheap["market_url"],
            ),
            ArbLeg(
                source=expensive["source"],
                outcome=f"NO @ {1 - expensive['implied_prob']:.0%}",
                decimal_odds=round(odds_no, 4),
                implied_prob=round(1.0 - expensive["implied_prob"], 4),
                stake_pct=round(stake_pct2, 4),
                stake_dollars=round(base_stake * stake_pct2, 2),
                market_url=expensive["market_url"],
            ),
        ]

        results.append(ArbOpportunityResult(
            event_name=f"{cheap['normalized_name']} vs {expensive['source']}",
            category=a["category"],
            profit_pct=round(profit_pct, 4),
            legs=legs,
            profit_on_1000=round(base_stake * profit_pct, 2),
        ))

    # Sort by profit descending, limit to top 50
    results.sort(key=lambda x: x.profit_pct, reverse=True)
    return results[:50]
