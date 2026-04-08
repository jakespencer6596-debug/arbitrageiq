"""
Manifold Markets prediction-market ingestion client.

Fetches open binary markets from the Manifold Markets API (no API key
required), filters by probability range, and persists every snapshot to
the MarketPrice and TrackedMarket tables.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import httpx
import logging
from datetime import datetime, timezone

from constants import MANIFOLD_API_URL, MANIFOLD_MIN_VOLUME
import constants
from db.models import SessionLocal, MarketPrice, TrackedMarket, SystemStatus
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)

_PAGE_LIMIT = 100
_MAX_PAGES = 6  # Increased for broader coverage


class ManifoldClient:
    """
    Async client for the Manifold Markets API.

    Paginates through open binary markets, filters by probability range,
    and writes normalised rows to the database.
    """

    def __init__(self) -> None:
        """Initialise with the Manifold Markets base URL from constants."""
        self.base_url = MANIFOLD_API_URL

    def _update_system_status(self, error: str | None = None) -> None:
        """
        Persist Manifold ingestor health information to SystemStatus.

        Args:
            error: If not None, the error message to record.
        """
        try:
            db = SessionLocal()
            try:
                status = (
                    db.query(SystemStatus)
                    .filter(SystemStatus.source == "manifold")
                    .first()
                )
                if not status:
                    status = SystemStatus(source="manifold", component="manifold")
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
                f"Could not update SystemStatus for manifold: {exc}"
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
            market_id: The Manifold market id.
            title: Human-readable market question.
            category: Classified category string.
        """
        existing = (
            db.query(TrackedMarket)
            .filter(
                TrackedMarket.source == "manifold",
                TrackedMarket.market_id == market_id,
            )
            .first()
        )
        if not existing:
            db.add(
                TrackedMarket(
                    source="manifold",
                    market_id=market_id,
                    event_name=title,
                    market_title=title,
                    category=category,
                    is_active=True,
                )
            )

    async def fetch(self) -> list[dict]:
        """
        Paginate through open Manifold Markets, filter by active category
        and quality thresholds, and return normalised rows.
        """
        results: list[dict] = []
        offset = 0
        page_count = 0

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                while page_count < _MAX_PAGES:
                    resp = await client.get(
                        f"{self.base_url}/search-markets",
                        params={
                            "term": "",
                            "sort": "liquidity",
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
                        # Skip resolved markets
                        if mkt.get("isResolved", False):
                            continue

                        # Extract probability -- only binary markets have this
                        probability = mkt.get("probability")
                        if probability is None:
                            continue

                        try:
                            probability = float(probability)
                        except (ValueError, TypeError):
                            continue

                        # Filter out extreme probabilities
                        if probability < 0.01 or probability > 0.99:
                            continue

                        # Quality filter: skip low-volume user-created markets
                        volume = mkt.get("volume", 0) or 0
                        if volume < MANIFOLD_MIN_VOLUME:
                            continue

                        market_id = str(mkt.get("id", ""))
                        if not market_id:
                            continue

                        question = mkt.get("question", "")
                        url = mkt.get("url", "")
                        resolution = mkt.get("resolution")
                        category = categorise(question)

                        yes_price = probability
                        no_price = round(1.0 - probability, 6)

                        results.append(
                            {
                                "source": "manifold",
                                "market_id": market_id,
                                "title": question,
                                "outcome": "yes",
                                "price": yes_price,
                                "category": category,
                                "volume": volume,
                                "timestamp": datetime.now(timezone.utc),
                                "yes_price": yes_price,
                                "no_price": no_price,
                                "url": url,
                                "raw": None,
                            }
                        )

                    page_count += 1

                    # If fewer than _PAGE_LIMIT returned, we've reached the end
                    if len(markets) < _PAGE_LIMIT:
                        break

                    offset += _PAGE_LIMIT

            logger.info(
                f"Fetched {len(results)} market rows from Manifold Markets"
            )

        except Exception as exc:
            logger.error(f"Manifold Markets fetch failed: {exc}")
            self._update_system_status(error=str(exc))
            return results

        logger.info(f"Manifold: {len(results)} rows across all categories")

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
                    # Upsert
                    existing = (
                        db.query(MarketPrice)
                        .filter(
                            MarketPrice.source == "manifold",
                            MarketPrice.market_id == r["market_id"],
                            MarketPrice.outcome == r["outcome"],
                        )
                        .first()
                    )
                    if existing:
                        existing.implied_probability = r["yes_price"]
                        existing.yes_price = r["yes_price"]
                        existing.no_price = r["no_price"]
                        existing.last_traded_price = r["price"]
                        existing.volume = r.get("volume")
                        existing.fetched_at = r["timestamp"]
                        existing.timestamp = r["timestamp"]
                        existing.is_active = True
                        existing.event_name = r["title"]
                        existing.category = r["category"]
                    else:
                        db.add(
                            MarketPrice(
                                source="manifold",
                                market_id=r["market_id"],
                                event_name=r["title"],
                                market_title=r["title"],
                                outcome=r["outcome"],
                                implied_probability=r["yes_price"],
                                category=r["category"],
                                yes_price=r["yes_price"],
                                no_price=r["no_price"],
                                last_traded_price=r["price"],
                                volume=r.get("volume"),
                                raw_payload=None,
                                fetched_at=r["timestamp"],
                                metadata_={"url": r["url"]} if r.get("url") else {},
                            )
                        )

                    mid = r["market_id"]
                    if mid not in seen_markets:
                        seen_markets.add(mid)
                        self._upsert_tracked_market(
                            db, mid, r["title"], r["category"]
                        )

                db.commit()
                logger.info(
                    f"Saved {len(results)} Manifold Markets prices to database"
                )
            finally:
                db.close()
        except Exception as exc:
            logger.error(f"Failed to save Manifold Markets data to DB: {exc}")
            self._update_system_status(error=str(exc))
            return results

        self._update_system_status()
        return results
