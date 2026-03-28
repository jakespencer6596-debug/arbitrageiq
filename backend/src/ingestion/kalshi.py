"""
Kalshi prediction-market ingestion client.

Paginates the Kalshi v2 markets endpoint, extracts YES/NO implied
probabilities from the order-book ask prices, and persists every snapshot
to the MarketPrice and TrackedMarket tables.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import asyncio
import httpx
import logging
from datetime import datetime, timezone

from constants import KALSHI_API_BASE, KEYWORD_MAP
from db.models import SessionLocal, MarketPrice, TrackedMarket, SystemStatus

logger = logging.getLogger(__name__)

_PAGE_LIMIT = 100
_MAX_PAGES = 10  # Cap pagination to avoid rate limits


def _categorise(title: str) -> str:
    """
    Map a market title to an ArbitrageIQ category using keyword matching.

    The function lowercases the title and checks every keyword defined in
    the project-wide KEYWORD_MAP.  The first match wins.  If nothing
    matches the category defaults to 'other'.

    Args:
        title: The human-readable market title.

    Returns:
        One of 'weather', 'economic', 'political', 'sports', or 'other'.
    """
    lower = title.lower() if title else ""
    for keyword, category in KEYWORD_MAP.items():
        if keyword in lower:
            return category
    return "other"


class KalshiClient:
    """
    Async client for the Kalshi trade-api/v2 markets endpoint.

    Paginates through all open markets, extracts implied YES/NO
    probabilities, and writes them to the database.
    """

    def __init__(self) -> None:
        """Initialise with the Kalshi base URL from constants."""
        self.base_url = KALSHI_API_BASE

    def _yes_probability(self, market: dict) -> float:
        """
        Derive the YES implied probability from a single Kalshi market dict.

        Handles both the legacy (cents) and current (dollar-string) API formats.

        Priority:
            1. ``yes_ask_dollars`` or ``yes_ask`` field.
            2. ``last_price_dollars`` or ``last_price`` field as fallback.
            3. 0.0 if neither is available.

        Args:
            market: A market dict from the Kalshi API response.

        Returns:
            A float between 0.0 and 1.0 representing the YES probability.
        """
        # New format: dollar strings like "0.4200"
        yes_ask_dollars = market.get("yes_ask_dollars")
        if yes_ask_dollars is not None:
            try:
                return float(yes_ask_dollars)
            except (ValueError, TypeError):
                pass

        # Legacy format: cents
        yes_ask = market.get("yes_ask")
        if yes_ask is not None:
            return float(yes_ask) / 100.0

        last_price_dollars = market.get("last_price_dollars")
        if last_price_dollars is not None:
            try:
                return float(last_price_dollars)
            except (ValueError, TypeError):
                pass

        last_price = market.get("last_price")
        if last_price is not None:
            return float(last_price) / 100.0

        return 0.0

    def _update_system_status(self, error: str | None = None) -> None:
        """
        Persist Kalshi ingestor health information to the SystemStatus table.

        Args:
            error: If not None, the error message to record.
        """
        try:
            db = SessionLocal()
            try:
                status = (
                    db.query(SystemStatus)
                    .filter(SystemStatus.source == "kalshi")
                    .first()
                )
                if not status:
                    status = SystemStatus(source="kalshi", component="kalshi")
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
            logger.debug(f"Could not update SystemStatus for kalshi: {exc}")

    def _upsert_tracked_market(
        self,
        db,
        market_id: str,
        title: str,
        category: str,
    ) -> None:
        """
        Insert or update a TrackedMarket row for auto-discovery.

        If a row with the same source + market_id already exists it is
        left unchanged.  Otherwise a new active TrackedMarket is created.

        Args:
            db: An active SQLAlchemy session.
            market_id: The Kalshi market ticker.
            title: Human-readable market title.
            category: Classified category string.
        """
        existing = (
            db.query(TrackedMarket)
            .filter(
                TrackedMarket.source == "kalshi",
                TrackedMarket.market_id == market_id,
            )
            .first()
        )
        if not existing:
            db.add(
                TrackedMarket(
                    source="kalshi",
                    market_id=market_id,
                    event_name=title,
                    market_title=title,
                    category=category,
                    is_active=True,
                )
            )

    async def fetch(self) -> list[dict]:
        """
        Paginate through all open Kalshi markets and return normalised rows.

        The method walks through pages using the ``cursor`` field returned
        by the API until no more pages remain.  For each market it:

        1. Derives YES probability from ``yes_ask`` (or ``last_price``).
        2. Computes NO probability as ``1 - yes``.
        3. Classifies the market into a category.
        4. Writes a MarketPrice row and upserts a TrackedMarket row.
        5. Updates SystemStatus on completion.

        Returns:
            A list of dicts with keys: source, market_id, title, yes_price,
            no_price, category, volume, timestamp.
        """
        results: list[dict] = []
        cursor: str | None = None
        page_count = 0

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                while page_count < _MAX_PAGES:
                    params: dict = {
                        "status": "open",
                        "limit": _PAGE_LIMIT,
                    }
                    if cursor:
                        params["cursor"] = cursor

                    resp = await client.get(
                        f"{self.base_url}/markets",
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    page_count += 1

                    markets = data.get("markets", [])
                    if not markets:
                        break

                    for mkt in markets:
                        ticker = mkt.get("ticker", "")
                        title = mkt.get("title", "")
                        yes_prob = self._yes_probability(mkt)
                        no_prob = 1.0 - yes_prob
                        category = _categorise(title)
                        volume = mkt.get("volume", 0)
                        open_interest = mkt.get("open_interest", 0)

                        results.append(
                            {
                                "source": "kalshi",
                                "market_id": ticker,
                                "title": title,
                                "yes_price": yes_prob,
                                "no_price": no_prob,
                                "category": category,
                                "volume": volume,
                                "open_interest": open_interest,
                                "timestamp": datetime.now(timezone.utc),
                                "raw": mkt,
                            }
                        )

                    # Advance pagination cursor
                    cursor = data.get("cursor")
                    if not cursor:
                        break

                    # Rate-limit between pages
                    await asyncio.sleep(0.3)

            logger.info(f"Fetched {len(results)} open markets from Kalshi")

        except Exception as exc:
            logger.error(f"Kalshi fetch failed: {exc}")
            self._update_system_status(error=str(exc))
            return results

        # ------------------------------------------------------------------
        # Persist to database
        # ------------------------------------------------------------------
        try:
            db = SessionLocal()
            try:
                for r in results:
                    db.add(
                        MarketPrice(
                            source="kalshi",
                            market_id=r["market_id"],
                            event_name=r["title"],
                            market_title=r["title"],
                            outcome="yes",
                            implied_probability=r["yes_price"],
                            category=r["category"],
                            yes_price=r["yes_price"],
                            no_price=r["no_price"],
                            volume=r.get("volume"),
                            open_interest=r.get("open_interest"),
                            raw_payload=r.get("raw"),
                            fetched_at=r["timestamp"],
                        )
                    )

                    # Auto-discover / track the market
                    self._upsert_tracked_market(
                        db,
                        r["market_id"],
                        r["title"],
                        r["category"],
                    )

                db.commit()
                logger.info(
                    f"Saved {len(results)} Kalshi prices to database"
                )
            finally:
                db.close()
        except Exception as exc:
            logger.error(f"Failed to save Kalshi data to DB: {exc}")
            self._update_system_status(error=str(exc))
            return results

        self._update_system_status()
        return results
