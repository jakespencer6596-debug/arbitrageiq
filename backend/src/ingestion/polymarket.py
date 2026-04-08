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

from constants import POLYMARKET_API_URL
import constants
from db.models import SessionLocal, MarketPrice, TrackedMarket, SystemStatus
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)

_PAGE_LIMIT = 100
_MAX_PAGES = 8  # Increased for broader coverage


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
        Paginate through open Polymarket markets, filter by active category,
        and return normalised rows.
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
                        category = categorise(question)

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
                                    "slug": slug,
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

        # Enrich with end_date from CLOB API (best-effort, non-blocking)
        try:
            async with httpx.AsyncClient(timeout=15) as clob_client:
                clob_resp = await clob_client.get(
                    "https://clob.polymarket.com/markets",
                    params={"limit": 500},
                )
                if clob_resp.status_code == 200:
                    clob_data = clob_resp.json().get("data", [])
                    # Build lookup: condition_id -> end_date
                    end_dates = {}
                    for cm in clob_data:
                        cid = cm.get("condition_id", "")
                        end = cm.get("end_date_iso", "")
                        if cid and end:
                            end_dates[cid] = end
                    # Attach end_date to results
                    for r in results:
                        r["end_date"] = end_dates.get(r["market_id"], "")
                    logger.info(f"Polymarket CLOB: enriched {sum(1 for r in results if r.get('end_date'))} markets with end_dates")
        except Exception as exc:
            logger.debug(f"Polymarket CLOB enrichment failed (non-fatal): {exc}")

        logger.info(f"Polymarket: {len(results)} rows across all categories")

        if not results:
            self._update_system_status()
            return results

        # ------------------------------------------------------------------
        # Persist to database
        # ------------------------------------------------------------------
        try:
            db = SessionLocal()
            try:
                seen_markets: set[str] = set()

                for r in results:
                    # Upsert: update existing row or insert new one
                    existing = (
                        db.query(MarketPrice)
                        .filter(
                            MarketPrice.source == "polymarket",
                            MarketPrice.market_id == r["market_id"],
                            MarketPrice.outcome == r["outcome"],
                        )
                        .first()
                    )
                    if existing:
                        existing.implied_probability = r.get("yes_price", r["price"])
                        existing.yes_price = r.get("yes_price")
                        existing.no_price = r.get("no_price")
                        existing.last_traded_price = r["price"]
                        existing.volume = r.get("volume")
                        existing.fetched_at = r["timestamp"]
                        existing.timestamp = r["timestamp"]
                        existing.is_active = True
                        existing.event_name = r["title"]
                        existing.category = r["category"]
                        existing.metadata_ = {"slug": r.get("slug", ""), "end_date": r.get("end_date", "")}
                    else:
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
                                metadata_={
                                    "slug": r.get("slug", ""),
                                    "end_date": r.get("end_date", ""),
                                },
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
