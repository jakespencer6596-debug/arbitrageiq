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

from dataclasses import dataclass, field
from constants import MIN_ARB_PROFIT_PCT, PLATFORM_FEES


def _get_fee_info(source: str) -> dict:
    """Get fee structure for a platform."""
    src = source.lower().strip()
    # Check for exact match or substring match (for bookmaker sources like "draftkings_h2h")
    if src in PLATFORM_FEES:
        return PLATFORM_FEES[src]
    for name, fees in PLATFORM_FEES.items():
        if name in src:
            return fees
    return {"trade_fee": 0.01, "withdrawal_fee": 0.0, "profit_fee": 0.0}


def _compute_net_profit(gross_profit: float, stake: float, source: str) -> float:
    """Compute net profit after platform fees."""
    fees = _get_fee_info(source)
    trade_cost = stake * fees.get("trade_fee", 0)
    profit_after_trade = gross_profit - trade_cost
    if profit_after_trade > 0:
        profit_after_trade -= profit_after_trade * fees.get("profit_fee", 0)
    withdrawal_cost = (stake + profit_after_trade) * fees.get("withdrawal_fee", 0)
    return profit_after_trade - withdrawal_cost


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
    volume: float = 0
    fees: dict = field(default_factory=dict)
    fetched_at: str = ""
    end_date: str = ""


@dataclass
class ArbOpportunityResult:
    """A detected arbitrage opportunity."""
    event_name: str
    category: str
    profit_pct: float
    legs: list
    profit_on_1000: float
    net_profit_pct: float = 0.0
    net_profit_on_1000: float = 0.0
    arb_type: str = "cross_platform"
    confidence: str = "medium"
    freshness_seconds: int = 0
    annualized_roi: float | None = None
    end_date: str = ""
    is_live: bool = False

    def to_dict(self) -> dict:
        """Serialize for JSON/DB storage."""
        return {
            "event_name": self.event_name,
            "category": self.category,
            "profit_pct": self.profit_pct,
            "net_profit_pct": self.net_profit_pct,
            "net_profit_on_1000": self.net_profit_on_1000,
            "arb_type": self.arb_type,
            "confidence": self.confidence,
            "freshness_seconds": self.freshness_seconds,
            "annualized_roi": self.annualized_roi,
            "end_date": self.end_date,
            "legs": [
                {
                    "source": leg.source,
                    "outcome": leg.outcome,
                    "decimal_odds": leg.decimal_odds,
                    "implied_prob": leg.implied_prob,
                    "stake_pct": leg.stake_pct,
                    "stake_dollars": leg.stake_dollars,
                    "market_url": leg.market_url,
                    "volume": leg.volume,
                    "fees": leg.fees,
                    "fetched_at": leg.fetched_at,
                    "end_date": leg.end_date,
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


def _fuzzy_similarity(name_a: str, name_b: str) -> float:
    """
    Compute similarity using rapidfuzz token_sort_ratio.
    Returns 0.0-1.0 scale. Handles word reordering and partial matches
    much better than Jaccard for prediction market event names.
    """
    try:
        from rapidfuzz import fuzz
        # token_sort_ratio sorts tokens alphabetically before comparing,
        # so "Trump wins 2028 election" matches "2028 election Trump wins"
        score = fuzz.token_sort_ratio(name_a.lower(), name_b.lower())
        return score / 100.0  # rapidfuzz returns 0-100, normalize to 0-1
    except ImportError:
        # Fallback to Jaccard if rapidfuzz not available
        return _similarity(_tokenize(name_a), _tokenize(name_b))


# ---------------------------------------------------------------------------
# Configurable thresholds — loosened in Phase 3 for 3-5x more matches
# ---------------------------------------------------------------------------
SIMILARITY_THRESHOLD = 0.40    # Jaccard minimum (coarse filter) — was 0.55
FUZZY_THRESHOLD = 50           # rapidfuzz token_sort_ratio minimum — was 60
MIN_SHARED_TOKENS = 2          # Must share at least 2 meaningful tokens — was 3
MAX_PROFIT_PCT = 0.25          # 25% cap — anything higher is a matching error

# ---------------------------------------------------------------------------
# Platform tiers — CRITICAL for product quality
# Only TRADEABLE platforms can form arb legs. Reference platforms
# feed into value signals/discrepancies but NOT arb detection.
# ---------------------------------------------------------------------------
TRADEABLE_SOURCES = frozenset({
    "polymarket", "kalshi", "predictit", "smarkets", "sxbet",
    "betfair", "matchbook", "cloudbet", "opinion",
    # Odds API sportsbooks
    "draftkings", "fanduel", "betmgm", "caesars", "pointsbet",
    "betrivers", "bovada", "bet365", "pinnacle",
    # Odds API IO bookmakers
    "odds_api", "odds_api_io",
})

REFERENCE_SOURCES = frozenset({
    "manifold", "metaculus", "gjopen", "infer", "fantasyscotus",
    "givewellopenphil", "foretold", "hypermind", "metaforecast",
    # Metaforecast sub-sources (stored with _mf suffix sometimes)
    "metaculus_mf", "gjopen_mf", "infer_mf", "fantasyscotus_mf",
    "givewellopenphil_mf", "foretold_mf", "hypermind_mf",
})

def _is_tradeable(source: str) -> bool:
    """Check if a source is a real-money tradeable platform."""
    src = source.lower().strip()
    if src in TRADEABLE_SOURCES:
        return True
    # Check substring match for sportsbook variants like "draftkings_h2h"
    for t in TRADEABLE_SOURCES:
        if t in src:
            return True
    return False


def _bigram_similarity(name_a: str, name_b: str) -> float:
    """
    Character bigram similarity — catches partial word matches that
    token-based methods miss (e.g., "Trump" vs "Trumps", "Biden" vs "Bidens").
    Returns 0.0-1.0.
    """
    def _bigrams(s: str) -> set[str]:
        s = s.lower().strip()
        return {s[i:i+2] for i in range(len(s) - 1)} if len(s) >= 2 else set()
    bg_a = _bigrams(name_a)
    bg_b = _bigrams(name_b)
    if not bg_a or not bg_b:
        return 0.0
    intersection = bg_a & bg_b
    union = bg_a | bg_b
    return len(intersection) / len(union)


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
            volume = price.get("volume", 0) or 0
            market_id = price.get("market_id", "")
            fetched_at = price.get("fetched_at", "")
            end_date = price.get("end_date", "")
        else:
            event_name = getattr(price, "event_name", "")
            outcome = getattr(price, "outcome", "")
            source = getattr(price, "source", "")
            implied_prob = getattr(price, "implied_probability", 0)
            raw_odds = getattr(price, "raw_odds", None)
            category = getattr(price, "category", "other")
            market_url = getattr(price, "market_url", "")
            volume = getattr(price, "volume", 0) or 0
            market_id = getattr(price, "market_id", "")
            fetched_at = getattr(price, "fetched_at", "") or ""
            end_date = ""

        if not event_name or not source or not implied_prob:
            continue
        if implied_prob <= 0.01 or implied_prob >= 0.99:
            continue  # Skip extreme prices (noise)

        # CRITICAL: Only tradeable platforms can form arb legs.
        # Reference sources (Metaculus, GJOpen, etc.) are for value
        # signals only — you can't place bets on them.
        if not _is_tradeable(source):
            continue

        # Skip events referencing past years (stale/resolved markets)
        import re as _re
        _past_years = {'2020', '2021', '2022', '2023', '2024'}
        _found_years = set(_re.findall(r'\b(20\d{2})\b', event_name))
        if _found_years and _found_years.issubset(_past_years):
            continue

        # PredictIt has 15% combined fees — arbs are shown with fee warnings
        # but NOT excluded, as users may have mitigation strategies

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
            "volume": volume,
            "market_id": market_id,
            "fetched_at": fetched_at,
            "end_date": end_date,
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

        # Require minimum shared token count (coarse filter)
        shared = a["tokens"] & b["tokens"]
        if len(shared) < MIN_SHARED_TOKENS:
            continue

        # Three-phase matching: coarse Jaccard + bigram + fine rapidfuzz
        jaccard = _similarity(a["tokens"], b["tokens"])
        if jaccard < SIMILARITY_THRESHOLD:
            continue

        # Bigram similarity for partial word matching
        bigram = _bigram_similarity(a["normalized_name"], b["normalized_name"])

        # Fine matching with rapidfuzz (handles word reordering, partial matches)
        fuzzy = _fuzzy_similarity(a["normalized_name"], b["normalized_name"])

        # Combined score: pass if fuzzy OR (jaccard + bigram are both strong)
        if fuzzy < FUZZY_THRESHOLD / 100.0 and not (jaccard >= 0.50 and bigram >= 0.50):
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

        # Compute fee-adjusted net profit
        stake1 = base_stake * stake_pct1
        stake2 = base_stake * stake_pct2
        gross_profit = base_stake * profit_pct
        # Net profit accounts for fees on BOTH legs
        net1 = _compute_net_profit(gross_profit * stake_pct1, stake1, cheap["source"])
        net2 = _compute_net_profit(gross_profit * stake_pct2, stake2, expensive["source"])
        net_profit = net1 + net2
        net_profit_pct = net_profit / base_stake if base_stake > 0 else 0

        # Show all arbs — even if fees eat the profit, users need to see them
        # The UI will show gross vs net so users can decide

        fee_info_cheap = _get_fee_info(cheap["source"])
        fee_info_expensive = _get_fee_info(expensive["source"])

        legs = [
            ArbLeg(
                source=cheap["source"],
                outcome=f"YES @ {cheap['implied_prob']:.0%}",
                decimal_odds=round(odds_yes, 4),
                implied_prob=round(cheap["implied_prob"], 4),
                stake_pct=round(stake_pct1, 4),
                stake_dollars=round(stake1, 2),
                market_url=cheap["market_url"],
                volume=cheap.get("volume", 0),
                fees=fee_info_cheap,
                fetched_at=cheap.get("fetched_at", ""),
                end_date=cheap.get("end_date", ""),
            ),
            ArbLeg(
                source=expensive["source"],
                outcome=f"NO @ {1 - expensive['implied_prob']:.0%}",
                decimal_odds=round(odds_no, 4),
                implied_prob=round(1.0 - expensive["implied_prob"], 4),
                stake_pct=round(stake_pct2, 4),
                stake_dollars=round(stake2, 2),
                market_url=expensive["market_url"],
                volume=expensive.get("volume", 0),
                fees=fee_info_expensive,
                fetched_at=expensive.get("fetched_at", ""),
                end_date=expensive.get("end_date", ""),
            ),
        ]

        # Flag if any leg uses play money
        has_play_money = any(
            _get_fee_info(l.source).get("is_play_money") for l in legs
        )

        # Compute freshness (max age of any leg in seconds)
        freshness = 0
        for leg in legs:
            if leg.fetched_at:
                try:
                    from datetime import datetime, timezone
                    fetched = datetime.fromisoformat(leg.fetched_at.replace("Z", "+00:00"))
                    age = (datetime.now(timezone.utc) - fetched).total_seconds()
                    freshness = max(freshness, int(age))
                except Exception:
                    pass

        # Compute annualized ROI from resolution date
        ann_roi = None
        arb_end_date = ""
        for leg in legs:
            if leg.end_date:
                arb_end_date = leg.end_date
                break
        if arb_end_date and net_profit_pct > 0:
            try:
                from datetime import datetime, timezone
                end_dt = datetime.fromisoformat(arb_end_date.replace("Z", "+00:00"))
                days = max(1, (end_dt - datetime.now(timezone.utc)).days)
                ann_roi = round((1 + net_profit_pct) ** (365.0 / days) - 1, 4)
            except Exception:
                pass

        # Enhanced confidence scoring — weighted across 4 dimensions
        min_vol = min(cheap.get("volume", 0), expensive.get("volume", 0))
        max_vol = max(cheap.get("volume", 0), expensive.get("volume", 0))

        # Match quality score (0-1): best of fuzzy and combined jaccard+bigram
        match_score = max(fuzzy, (jaccard + bigram) / 2)

        # Volume score (0-1): log scale, 0 at vol=0, 1 at vol=100K+
        import math
        vol_score = min(1.0, math.log10(max(min_vol, 1)) / 5.0)

        # Freshness score (0-1): 1.0 if <60s, decays to 0 at 30min
        fresh_score = max(0.0, 1.0 - (freshness / 1800.0))

        # Platform reliability — real-money platforms score higher
        _RELIABLE = {"polymarket", "kalshi", "smarkets", "betfair", "predictit"}
        both_reliable = cheap["source"] in _RELIABLE and expensive["source"] in _RELIABLE
        reliability_score = 1.0 if both_reliable else 0.6

        # Weighted confidence: match 40%, volume 25%, freshness 20%, reliability 15%
        conf_score = (match_score * 0.40 + vol_score * 0.25 +
                      fresh_score * 0.20 + reliability_score * 0.15)

        if conf_score >= 0.70:
            confidence = "high"
        elif conf_score >= 0.45:
            confidence = "medium"
        else:
            confidence = "low"

        results.append(ArbOpportunityResult(
            event_name=f"{cheap['normalized_name']} vs {expensive['source']}",
            category=a["category"],
            profit_pct=round(profit_pct, 4),
            net_profit_pct=round(net_profit_pct, 4),
            net_profit_on_1000=round(net_profit, 2),
            arb_type="play_money" if has_play_money else "cross_platform",
            confidence=confidence,
            freshness_seconds=freshness,
            annualized_roi=ann_roi,
            end_date=arb_end_date,
            legs=legs,
            profit_on_1000=round(base_stake * profit_pct, 2),
        ))

    # Sort by NET profit descending, limit to top 50
    results.sort(key=lambda x: x.net_profit_pct, reverse=True)
    return results[:50]


# ---------------------------------------------------------------------------
# Multi-outcome arb detection — 3+ way markets across platforms
# ---------------------------------------------------------------------------

def detect_multi_outcome_arb(market_prices: list, base_stake: float = 1000.0) -> list[ArbOpportunityResult]:
    """
    Detect arbitrage in N-way markets (3+ outcomes) across platforms.

    Example: "Who will win the 2028 presidential election?"
    - Polymarket: Trump 45%, DeSantis 20%, Newsom 15%, Field 20%
    - PredictIt: Trump 50%, DeSantis 18%, Newsom 12%, Field 20%

    If we can buy the cheapest price for each candidate across platforms
    and the sum of implied probs < 1.0, that's a guaranteed-profit arb.

    Strategy:
    1. Group by parent market (using market_id prefix or event name)
    2. For each candidate/outcome, find the cheapest price across all sources
    3. Check if sum of cheapest implied probs < 1.0
    """
    from collections import defaultdict

    # Parse prices with outcome info
    parsed = []
    for price in market_prices:
        if isinstance(price, dict):
            event_name = price.get("event_name", "")
            outcome = price.get("outcome", "yes")
            source = price.get("source", "").lower().strip()
            prob = price.get("implied_probability", 0)
            market_url = price.get("market_url", "")
            volume = price.get("volume", 0) or 0
            category = price.get("category", "other")
            market_id = price.get("market_id", "")
            fetched_at = price.get("fetched_at", "")
        else:
            event_name = getattr(price, "event_name", "")
            outcome = getattr(price, "outcome", "yes")
            source = getattr(price, "source", "").lower().strip()
            prob = getattr(price, "implied_probability", 0)
            market_url = getattr(price, "market_url", "")
            volume = getattr(price, "volume", 0) or 0
            category = getattr(price, "category", "other")
            market_id = getattr(price, "market_id", "")
            fetched_at = getattr(price, "fetched_at", "") or ""

        if not event_name or not source or not prob or prob <= 0.01 or prob >= 0.99:
            continue
        # Only tradeable platforms
        if not _is_tradeable(source):
            continue
        # Skip simple yes/no — we want named outcomes (candidates, teams)
        outcome_lower = (outcome or "").lower().strip()
        if outcome_lower in ("yes", "no", ""):
            continue

        parsed.append({
            "event_name": _normalize_event_name(event_name),
            "outcome": outcome_lower,
            "source": source,
            "prob": prob,
            "odds": 1.0 / prob,
            "market_url": market_url,
            "volume": volume,
            "category": category,
            "market_id": market_id,
            "fetched_at": fetched_at,
        })

    if len(parsed) < 3:
        return []

    # Group by normalized event name (the parent market)
    event_groups: dict[str, list] = defaultdict(list)
    for p in parsed:
        # Use first 80 chars of event name as group key
        key = p["event_name"][:80].lower()
        event_groups[key].append(p)

    # For similar event names, merge groups using fuzzy matching
    keys = list(event_groups.keys())
    merged = {}
    used = set()
    for i, k1 in enumerate(keys):
        if k1 in used:
            continue
        group = list(event_groups[k1])
        for k2 in keys[i+1:]:
            if k2 in used:
                continue
            sim = _fuzzy_similarity(k1, k2)
            if sim >= 0.60:
                group.extend(event_groups[k2])
                used.add(k2)
        merged[k1] = group
        used.add(k1)

    results = []

    for event_key, prices in merged.items():
        # Need prices from 2+ sources with 3+ distinct outcomes
        sources = set(p["source"] for p in prices)
        outcomes = set(p["outcome"] for p in prices)
        if len(sources) < 2 or len(outcomes) < 3:
            continue

        # For each outcome, find the cheapest implied probability across sources
        outcome_best: dict[str, dict] = {}  # outcome -> cheapest price dict
        for p in prices:
            oc = p["outcome"]
            if oc not in outcome_best or p["prob"] < outcome_best[oc]["prob"]:
                outcome_best[oc] = p

        # Check if sum of cheapest probs < 1.0 (arb condition)
        cheapest_probs = [v["prob"] for v in outcome_best.values()]
        arb_sum = sum(cheapest_probs)

        if arb_sum >= 1.0:
            continue  # No arb

        profit_pct = (1.0 / arb_sum) - 1.0
        if profit_pct > MAX_PROFIT_PCT or profit_pct < MIN_ARB_PROFIT_PCT:
            continue

        # Build legs
        legs = []
        total_net = 0.0
        for oc, best in outcome_best.items():
            stake_pct = (1.0 / best["odds"]) / arb_sum
            stake = base_stake * stake_pct
            gross_leg = base_stake * profit_pct * stake_pct
            net_leg = _compute_net_profit(gross_leg, stake, best["source"])
            total_net += net_leg

            fee_info = _get_fee_info(best["source"])
            legs.append(ArbLeg(
                source=best["source"],
                outcome=f"BUY {oc} @ {best['prob']:.0%}",
                decimal_odds=round(best["odds"], 4),
                implied_prob=round(best["prob"], 4),
                stake_pct=round(stake_pct, 4),
                stake_dollars=round(stake, 2),
                market_url=best["market_url"],
                volume=best["volume"],
                fees=fee_info,
                fetched_at=best.get("fetched_at", ""),
            ))

        net_profit_pct = total_net / base_stake if base_stake > 0 else 0
        # Use first price's category and event name
        sample = list(outcome_best.values())[0]

        results.append(ArbOpportunityResult(
            event_name=f"[Multi-{len(outcomes)}way] {sample['event_name'][:80]}",
            category=sample["category"],
            profit_pct=round(profit_pct, 4),
            net_profit_pct=round(net_profit_pct, 4),
            net_profit_on_1000=round(total_net, 2),
            arb_type="multi_outcome",
            confidence="medium",
            legs=legs,
            profit_on_1000=round(base_stake * profit_pct, 2),
        ))

    results.sort(key=lambda x: x.net_profit_pct, reverse=True)
    return results[:20]


# ---------------------------------------------------------------------------
# Overround detection — arbs within a single platform
# ---------------------------------------------------------------------------

def detect_overround(market_prices: list, base_stake: float = 1000.0) -> list[ArbOpportunityResult]:
    """
    Detect same-market overround arbs on a single platform.

    When multiple contracts in one market (e.g., PredictIt "Who will win?")
    have YES prices summing to > 100%, you can sell all contracts for
    guaranteed profit. When they sum to < 100%, you can buy all for guaranteed profit.

    This does NOT require cross-platform matching — works on a single source.
    """
    from collections import defaultdict

    # Group prices by (source, market_id_prefix)
    # PredictIt uses "marketid_contractid" format
    market_groups: dict[str, list[dict]] = defaultdict(list)

    for price in market_prices:
        if isinstance(price, dict):
            source = price.get("source", "").lower().strip()
            market_id = price.get("market_id", "")
            event_name = price.get("event_name", "")
            implied_prob = price.get("implied_probability", 0)
            market_url = price.get("market_url", "")
            volume = price.get("volume", 0) or 0
            category = price.get("category", "other")
        else:
            source = getattr(price, "source", "").lower().strip()
            market_id = getattr(price, "market_id", "")
            event_name = getattr(price, "event_name", "")
            implied_prob = getattr(price, "implied_probability", 0)
            market_url = getattr(price, "market_url", "")
            volume = getattr(price, "volume", 0) or 0
            category = getattr(price, "category", "other")

        if not market_id or not implied_prob or implied_prob <= 0:
            continue

        # Only tradeable platforms for overrounds
        if not _is_tradeable(source):
            continue

        # Only detect overrounds on multi-candidate platforms
        # Skip Polymarket (binary YES/NO markets, not multi-candidate)
        if source in ("polymarket",):
            continue

        # Extract the parent market ID (before "_" for PredictIt)
        if source == "predictit" and "_" in market_id:
            parent_id = market_id.split("_")[0]
        else:
            parent_id = market_id

        group_key = f"{source}:{parent_id}"
        market_groups[group_key].append({
            "source": source,
            "market_id": market_id,
            "event_name": event_name,
            "implied_prob": implied_prob,
            "market_url": market_url,
            "volume": volume,
            "category": category,
        })

    results = []
    for group_key, contracts in market_groups.items():
        if len(contracts) < 2:
            continue  # Need multiple contracts

        # Sum of all YES implied probabilities
        total_prob = sum(c["implied_prob"] for c in contracts)

        # If total > 1.0, selling all contracts gives guaranteed profit
        # PredictIt has 15% fees, so need higher overround to be profitable
        min_overround = 1.20 if contracts[0]["source"] == "predictit" else 1.05
        if total_prob > min_overround:
            overround = total_prob - 1.0
            profit_pct = overround / total_prob  # ROI on total capital needed

            source = contracts[0]["source"]
            category = contracts[0]["category"]
            # Use the market name from the first contract (strip contract suffix)
            market_name = contracts[0]["event_name"]
            if " -- " in market_name:
                market_name = market_name.split(" -- ")[0]

            fee_info = _get_fee_info(source)
            legs = []
            for c in contracts:
                contract_name = c["event_name"]
                if " -- " in contract_name:
                    contract_name = contract_name.split(" -- ")[1]
                legs.append(ArbLeg(
                    source=c["source"],
                    outcome=f"SELL {contract_name} @ {c['implied_prob']:.0%}",
                    decimal_odds=round(1.0 / c["implied_prob"], 4) if c["implied_prob"] > 0 else 0,
                    implied_prob=round(c["implied_prob"], 4),
                    stake_pct=round(c["implied_prob"] / total_prob, 4),
                    stake_dollars=round(base_stake * c["implied_prob"] / total_prob, 2),
                    market_url=c["market_url"],
                    volume=c["volume"],
                    fees=fee_info,
                ))

            # Net profit after fees — compute per-leg for overrounds
            # Each leg is a separate contract with its own fees
            gross = base_stake * profit_pct
            fees = _get_fee_info(source)
            total_fees = 0
            for leg in legs:
                leg_stake = leg.stake_dollars
                leg_profit = leg_stake * (leg.decimal_odds - 1) if leg.decimal_odds > 1 else 0
                trade_cost = leg_stake * fees.get("trade_fee", 0)
                profit_fee = leg_profit * fees.get("profit_fee", 0) if leg_profit > 0 else 0
                wd_fee = (leg_stake + leg_profit) * fees.get("withdrawal_fee", 0)
                total_fees += trade_cost + profit_fee + wd_fee
            net = gross - total_fees
            net_pct = net / base_stake if base_stake > 0 else 0

            if net_pct > 0.005:  # 0.5% minimum to be worth the effort
                results.append(ArbOpportunityResult(
                    event_name=f"[Overround] {market_name} ({source})",
                    category=category,
                    profit_pct=round(profit_pct, 4),
                    net_profit_pct=round(net_pct, 4),
                    net_profit_on_1000=round(net, 2),
                    arb_type="overround",
                    legs=legs,
                    profit_on_1000=round(gross, 2),
                ))

    results.sort(key=lambda x: x.net_profit_pct, reverse=True)
    return results[:20]
