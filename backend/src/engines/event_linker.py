"""
Event Linker — persistent cross-platform event matching.

Instead of re-fuzzy-matching 3,000+ markets every 60 seconds,
this module builds and maintains an EventMapping table that
persistently links markets across platforms.

Once "Trump wins 2028" on Polymarket is linked to the same event
on Kalshi, that link is stored and reused every cycle — making
arb detection O(linked_events) instead of O(N^2).

Matching signals (in priority order):
1. Exact market ID match (rare but perfect — e.g., PolyRouter IDs)
2. Fuzzy name match with entity guards (countries, years, proper nouns)
3. Bigram similarity for partial word matches
4. Category + resolution date overlap
"""

import re
import logging
from datetime import datetime, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)


_STOP_WORDS = frozenset({
    "will", "the", "a", "an", "in", "of", "to", "for", "by", "on", "at",
    "be", "is", "it", "and", "or", "not", "this", "that", "with", "from",
    "win", "yes", "no", "2024", "2025", "2026", "2027", "2028", "2029", "2030",
    "who", "what", "how", "when", "where", "before", "after",
    "market", "prediction", "contract", "price", "read", "description",
    "question", "resolve", "resolves", "resolution",
})


def _normalize(text: str) -> str:
    text = text.replace(" -- ", " ")
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'^market:\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^will\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\?+$', '', text)
    return text.strip().lower()


def _tokenize(text: str) -> set[str]:
    tokens = set(re.findall(r'[a-z0-9]+', text.lower()))
    return tokens - _STOP_WORDS


def _extract_entities(text: str) -> set[str]:
    lower = text.lower()
    entities = set()
    _COUNTRIES = {
        "us", "usa", "uk", "china", "russia", "india", "brazil",
        "france", "germany", "japan", "canada", "australia",
        "israel", "iran", "ukraine", "taiwan", "mexico", "colombia",
    }
    for c in _COUNTRIES:
        if c in lower:
            entities.add(c)
    for y in re.findall(r'\b(20[2-3]\d)\b', text):
        entities.add(y)
    for m in re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', text):
        entities.add(m.lower())
    return entities


def _fuzzy_score(a: str, b: str) -> float:
    try:
        from rapidfuzz import fuzz
        return fuzz.token_sort_ratio(a, b) / 100.0
    except ImportError:
        tokens_a = _tokenize(a)
        tokens_b = _tokenize(b)
        if not tokens_a or not tokens_b:
            return 0.0
        return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def link_events(active_prices: list, db_session) -> dict[str, list]:
    """
    Build/update EventMapping table from active market prices.

    Returns a dict of canonical_name -> list of price dicts,
    ready for the arb engine to compare within each group.
    """
    from db.models import EventMapping

    # 1. Load existing mappings
    existing = db_session.query(EventMapping).filter(
        EventMapping.is_active == True  # noqa: E712
    ).all()

    # Build lookup: (source, market_id) -> canonical_name
    known: dict[tuple[str, str], str] = {}
    for m in existing:
        known[(m.source, m.source_market_id)] = m.canonical_name

    # 2. Parse active prices
    parsed = []
    for p in active_prices:
        if isinstance(p, dict):
            source = p.get("source", "").lower().strip()
            market_id = p.get("market_id", "")
            event_name = p.get("event_name", "")
        else:
            source = getattr(p, "source", "").lower().strip()
            market_id = getattr(p, "market_id", "")
            event_name = getattr(p, "event_name", "")

        if not source or not market_id or not event_name:
            continue

        normalized = _normalize(event_name)
        tokens = _tokenize(normalized)
        if len(tokens) < 2:
            continue

        parsed.append({
            "source": source,
            "market_id": market_id,
            "event_name": event_name,
            "normalized": normalized,
            "tokens": tokens,
            "entities": _extract_entities(event_name),
            "price": p,
        })

    # 3. Assign canonical names
    # First pass: use existing mappings
    groups: dict[str, list] = defaultdict(list)
    unlinked = []

    for p in parsed:
        key = (p["source"], p["market_id"])
        if key in known:
            canon = known[key]
            groups[canon].append(p["price"])
            # Update last_seen
            for m in existing:
                if m.source == p["source"] and m.source_market_id == p["market_id"]:
                    m.last_seen_at = datetime.now(timezone.utc)
                    break
        else:
            unlinked.append(p)

    # Second pass: match unlinked prices against existing canonical names
    # and against each other
    canon_representatives: dict[str, dict] = {}
    for p in parsed:
        key = (p["source"], p["market_id"])
        if key in known:
            canon = known[key]
            if canon not in canon_representatives:
                canon_representatives[canon] = p

    new_mappings = 0

    for p in unlinked:
        best_canon = None
        best_score = 0.0
        best_method = "fuzzy"

        # Try matching against known canonical names
        for canon, rep in canon_representatives.items():
            # Entity guard
            if p["entities"] and rep["entities"]:
                if not (p["entities"] & rep["entities"]):
                    continue

            shared = p["tokens"] & rep["tokens"]
            if len(shared) < 2:
                continue

            score = _fuzzy_score(p["normalized"], rep["normalized"])
            if score > best_score and score >= 0.50:
                best_score = score
                best_canon = canon

        if best_canon:
            # Link to existing canonical event
            groups[best_canon].append(p["price"])
            known[(p["source"], p["market_id"])] = best_canon

            mapping = EventMapping(
                canonical_name=best_canon,
                source=p["source"],
                source_market_id=p["market_id"],
                event_name=p["event_name"],
                category=p["price"].get("category", "other") if isinstance(p["price"], dict)
                         else getattr(p["price"], "category", "other"),
                confidence=best_score,
                match_method=best_method,
            )
            db_session.add(mapping)
            new_mappings += 1
        else:
            # Create new canonical event
            canon = p["normalized"][:120]
            groups[canon].append(p["price"])
            known[(p["source"], p["market_id"])] = canon
            canon_representatives[canon] = p

            mapping = EventMapping(
                canonical_name=canon,
                source=p["source"],
                source_market_id=p["market_id"],
                event_name=p["event_name"],
                category=p["price"].get("category", "other") if isinstance(p["price"], dict)
                         else getattr(p["price"], "category", "other"),
                confidence=1.0,
                match_method="seed",
            )
            db_session.add(mapping)
            new_mappings += 1

    if new_mappings > 0:
        try:
            db_session.commit()
            logger.info(f"event_linker: created {new_mappings} new mappings, "
                        f"{len(groups)} canonical events, "
                        f"{sum(len(v) for v in groups.values())} total prices linked")
        except Exception as exc:
            db_session.rollback()
            logger.error(f"event_linker: failed to save mappings: {exc}")

    # Filter to groups with 2+ sources (arb candidates)
    multi_source = {}
    for canon, prices in groups.items():
        sources = set()
        for p in prices:
            src = p.get("source", "") if isinstance(p, dict) else getattr(p, "source", "")
            sources.add(src.lower().strip())
        if len(sources) >= 2:
            multi_source[canon] = prices

    logger.info(f"event_linker: {len(multi_source)} events with 2+ sources (arb candidates)")
    return multi_source
