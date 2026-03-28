"""
Polymarket prediction-market ingestion client.

Paginates the Gamma API, parses the JSON-encoded ``outcomePrices`` and
``outcomes`` strings, and persists every snapshot to the MarketPrice and
TrackedMarket tables.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
import httpx
import logging
from datetime import datetime, timezone

from constants import POLYMARKET_API_URL, KEYWORD_MAP
from db.models import SessionLocal, MarketPrice, TrackedMarket, SystemStatus

logger = logging.getLogger(__name__)

_PAGE_LIMIT = 100
_MAX_PAGES = 5  # Cap pagination to avoid OOM on free tier


def _categorise(title: str) -> str:
    """
    Map a market title to an ArbitrageIQ category using keyword matching.

    The function lowercases the title and checks every keyword defined in
    the project-wide KEYWORD_MAP.  The first match wins.  If nothing
    matches the category defaults to 'other'.

    Args:
        title: The human-readable market question.

    Returns:
        One of 'weather', 'economic', 'political', 'sports', or 'other'.
    """
    lower = title.lower() if title else ""
    for keyword, category in KEYWORD_MAP.items():
        if keyword in lower:
            return category
    return "other"


def _parse_json_string(value) -> list:
    """
    Safely parse a JSON-encoded string into a Python list.

    Polymarket encodes ``outcomePrices`` and ``outcomes`` as JSON strings
    (e.g. ``'["0.45", "0.55"]'``).  This helper handles both actual
    strings and values that are already decoded as lists.

    Args:
        value: Either a JSON string or an already-decoded list.

    Returns:
        A Python list.  Returns an empty list on failure.
    """
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


class PolymarketClient:
    """
    Async client for the Polymarket Gamma API.

    Paginates through all open markets, parses the JSON-encoded outcome
    prices, and writes normalised rows to the database.
    """

    def __init__(self) -> None:
        """Initialise with the Polymarket base URL from constants."""
        self.base_url = POLYMARKET_API_URL

    def _update_system_status(self, error: str | None = None) -> None:
        """
        Persist Polymarket ingestor health information to SystemStatus.

        Args:
            error: If not None, the error message to record.
        """
        try:
            db = SessionLocal()
            try:
                status = (
                    db.query(SystemStatus)
                    .filter(SystemStatus.source == "polymarket")
                    .first()
                )
                if not status:
                    status = SystemStatus(source="polymarket", component="polymarket")
                    db.add(status)

                now = datetime.now(timezone.utc)

                if error:
                    status.status = "degraded"
                    status.last_failure_at = now
                    status.last_error = error
                    status.consecutive_failures = (
                        (status.consecutive_failures or 0) + 1
                    )
                else:
                    status.status = "healthy"
                    status.last_success_at = now
                    status.consecutive_failures = 0

                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.debug(
                f"Could not update SystemStatus for polymarket: {exc}"
            )

    def _upsert_tracked_market(
        self,
        db,
        market_id: str,
        title: str,
        category: str,
    ) -> None:
        """
        Insert or update a TrackedMarket row for auto-discovery.

        If a row with the same source and market_id already exists it is
        left unchanged.  Otherwise a new active TrackedMarket is created.

        Args:
            db: An active SQLAlchemy session.
            market_id: The Polymarket condition_id or slug.
            title: Human-readable market question.
            category: Classified category string.
        """
        existing = (
            db.query(TrackedMarket)
            .filter(
                TrackedMarket.source == "polymarket",
                TrackedMarket.market_id == market_id,
            )
            .first()
        )
        if not existing:
            db.add(
                TrackedMarket(
                    source="polymarket",
                    market_id=market_id,
                    event_name=title,
                    market_title=title,
                    category=category,
                    is_active=True,
                )
            )

    async def fetch(self) -> list[dict]:
        """
        Paginate through all open Polymarket markets and return normalised rows.

        The endpoint returns up to 100 markets per page.  The method
        increments ``offset`` by 100 until a page returns fewer than 100
        results or an empty list.

        For each market:
            1. ``outcomePrices`` is a **JSON-encoded string** like
               ``'["0.45","0.55"]'`` -- it must be parsed with
               ``json.loads()``.
            2. ``outcomes`` is similarly encoded (e.g. ``'["Yes","No"]'``).
            3. Each (outcome, price) pair is written as a MarketPrice row.
            4. New markets are auto-tracked via TrackedMarket upsert.

        Returns:
            A list of dicts with keys: source, market_id, title, outcome,
            price, category, volume, timestamp.
        """
        results: list[dict] = []
        offset = 0
        page_count = 0

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                while page_count < _MAX_PAGES:
                    resp = await client.get(
                        f"{self.base_url}/markets",
                        params={
                            "closed": "false",
                            "limit": _PAGE_LIMIT,
                            "offset": offset,
                        },
                    )
                    resp.raise_for_status()
                    markets = resp.json()

                    # The endpoint returns a plain JSON array
                    if not isinstance(markets, list):
                        markets = markets.get("data", [])

                    if not markets:
                        break

                    for mkt in markets:
                        condition_id = mkt.get("condition_id") or mkt.get(
                            "id", ""
                        )
                        question = mkt.get("question", "") or mkt.get(
                            "title", ""
                        )
                        slug = mkt.get("slug", "")
                        market_id = str(condition_id) if condition_id else slug
                        volume = mkt.get("volume", 0)
                        category = _categorise(question)

                        # -------------------------------------------------
                        # CRITICAL: outcomePrices is a JSON-encoded STRING
                        # -------------------------------------------------
                        outcome_prices = _parse_json_string(
                            mkt.get("outcomePrices")
                        )
                        outcome_labels = _parse_json_string(
                            mkt.get("outcomes")
                        )

                        if not outcome_prices:
                            continue

                        # Ensure labels list is at least as long as prices
                        while len(outcome_labels) < len(outcome_prices):
                            outcome_labels.append(f"Outcome_{len(outcome_labels)}")

                        yes_price: float | None = None
                        no_price: float | None = None

                        for idx, raw_price in enumerate(outcome_prices):
                            try:
                                price = float(raw_price)
                            except (ValueError, TypeError):
                                price = 0.0

                            label = outcome_labels[idx] if idx < len(outcome_labels) else f"Outcome_{idx}"

                            # Track yes/no for the MarketPrice record
                            label_lower = label.lower()
                            if label_lower == "yes" or idx == 0:
                                yes_price = price
                            if label_lower == "no" or idx == 1:
                                no_price = price

                            results.append(
                                {
                                    "source": "polymarket",
                                    "market_id": market_id,
                                    "title": question,
                                    "outcome": label,
                                    "price": price,
                                    "category": category,
                                    "volume": volume,
                                    "timestamp": datetime.now(timezone.utc),
                                    "yes_price": yes_price,
                                    "no_price": no_price,
                                    "raw": None,
                                }
                            )

                    page_count += 1

                    # If fewer than _PAGE_LIMIT returned, we've reached the end
                    if len(markets) < _PAGE_LIMIT:
                        break

                    offset += _PAGE_LIMIT

            logger.info(
                f"Fetched {len(results)} outcome rows from Polymarket"
            )

        except Exception as exc:
            logger.error(f"Polymarket fetch failed: {exc}")
            self._update_system_status(error=str(exc))
            return results

        # ------------------------------------------------------------------
        # Persist to database
        # ------------------------------------------------------------------
        try:
            db = SessionLocal()
            try:
                seen_markets: set[str] = set()

                for r in results:
                    db.add(
                        MarketPrice(
                            source="polymarket",
                            market_id=r["market_id"],
                            event_name=r["title"],
                            market_title=r["title"],
                            outcome=r["outcome"],
                            implied_probability=r.get("yes_price", r["price"]),
                            category=r["category"],
                            yes_price=r.get("yes_price"),
                            no_price=r.get("no_price"),
                            last_traded_price=r["price"],
                            volume=r.get("volume"),
                            raw_payload=r.get("raw"),
                            fetched_at=r["timestamp"],
                        )
                    )

                    # Auto-discover -- only upsert once per market
                    mid = r["market_id"]
                    if mid not in seen_markets:
                        seen_markets.add(mid)
                        self._upsert_tracked_market(
                            db, mid, r["title"], r["category"]
                        )

                db.commit()
                logger.info(
                    f"Saved {len(results)} Polymarket prices to database"
                )
            finally:
                db.close()
        except Exception as exc:
            logger.error(f"Failed to save Polymarket data to DB: {exc}")
            self._update_system_status(error=str(exc))
            return results

        self._update_system_status()
        return results
