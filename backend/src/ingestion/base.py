"""
Base ingestion client class.

Provides shared upsert logic, system status tracking, and circuit breaker
so new data source integrations are concise and consistent.
"""

import logging
from datetime import datetime, timezone, timedelta

from db.models import SessionLocal, MarketPrice, TrackedMarket, SystemStatus
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)


class BaseClient:
    """
    Abstract base class for all ingestion clients.

    Subclasses must implement:
        source_name: str          — e.g. "opinion", "betfair"
        async def _fetch_raw()    — return list[dict] of raw market data

    Each raw dict should have at minimum:
        market_id, title, yes_price, category, timestamp
    Optional: no_price, outcome, volume, open_interest, metadata
    """

    source_name: str = ""
    circuit_breaker_threshold: int = 10
    circuit_breaker_reset_hours: int = 1

    def _update_system_status(self, error: str | None = None) -> None:
        """Persist health information to SystemStatus."""
        try:
            db = SessionLocal()
            try:
                status = (
                    db.query(SystemStatus)
                    .filter(SystemStatus.source == self.source_name)
                    .first()
                )
                if not status:
                    status = SystemStatus(
                        source=self.source_name,
                        component=self.source_name,
                    )
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
                f"Could not update SystemStatus for {self.source_name}: {exc}"
            )

    def _check_circuit_breaker(self) -> bool:
        """Return True if the circuit breaker is tripped (should skip)."""
        try:
            db = SessionLocal()
            status = (
                db.query(SystemStatus)
                .filter(SystemStatus.source == self.source_name)
                .first()
            )
            if status and (status.consecutive_failures or 0) >= self.circuit_breaker_threshold:
                if status.last_failure_at:
                    age = datetime.now(timezone.utc) - status.last_failure_at.replace(
                        tzinfo=timezone.utc
                    )
                    if age > timedelta(hours=self.circuit_breaker_reset_hours):
                        status.consecutive_failures = 0
                        db.commit()
                        db.close()
                        logger.info(
                            f"{self.source_name}: circuit breaker reset"
                        )
                        return False
                db.close()
                logger.debug(
                    f"{self.source_name}: circuit breaker active, skipping"
                )
                return True
            db.close()
        except Exception:
            pass
        return False

    def _upsert_price(self, db, row: dict) -> None:
        """Insert or update a MarketPrice row."""
        source = row.get("source", self.source_name)
        market_id = row["market_id"]
        outcome = row.get("outcome", "yes")

        existing = (
            db.query(MarketPrice)
            .filter(
                MarketPrice.source == source,
                MarketPrice.market_id == market_id,
                MarketPrice.outcome == outcome,
            )
            .first()
        )

        if existing:
            existing.implied_probability = row.get("yes_price")
            existing.yes_price = row.get("yes_price")
            existing.no_price = row.get("no_price")
            existing.volume = row.get("volume")
            existing.open_interest = row.get("open_interest")
            existing.fetched_at = row.get("timestamp", datetime.now(timezone.utc))
            existing.timestamp = row.get("timestamp", datetime.now(timezone.utc))
            existing.is_active = True
            existing.event_name = row.get("title", existing.event_name)
            existing.category = row.get("category", existing.category)
            if row.get("metadata"):
                existing.metadata_ = row["metadata"]
            if row.get("last_traded_price"):
                existing.last_traded_price = row["last_traded_price"]
            if row.get("raw_odds"):
                existing.raw_odds = row["raw_odds"]
        else:
            db.add(
                MarketPrice(
                    source=source,
                    market_id=market_id,
                    event_name=row.get("title", ""),
                    market_title=row.get("title", ""),
                    outcome=outcome,
                    implied_probability=row.get("yes_price"),
                    category=row.get("category", "other"),
                    yes_price=row.get("yes_price"),
                    no_price=row.get("no_price"),
                    volume=row.get("volume"),
                    open_interest=row.get("open_interest"),
                    raw_odds=row.get("raw_odds"),
                    last_traded_price=row.get("last_traded_price"),
                    raw_payload=None,
                    fetched_at=row.get("timestamp", datetime.now(timezone.utc)),
                    metadata_=row.get("metadata", {}),
                )
            )

    def _upsert_tracked_market(self, db, market_id: str, title: str, category: str) -> None:
        """Insert or update a TrackedMarket row."""
        existing = (
            db.query(TrackedMarket)
            .filter(
                TrackedMarket.source == self.source_name,
                TrackedMarket.market_id == market_id,
            )
            .first()
        )
        if not existing:
            db.add(
                TrackedMarket(
                    source=self.source_name,
                    market_id=market_id,
                    event_name=title,
                    market_title=title,
                    category=category,
                    is_active=True,
                )
            )

    async def _fetch_raw(self) -> list[dict]:
        """Subclasses implement this to return raw market data."""
        raise NotImplementedError

    async def fetch(self) -> list[dict]:
        """
        Main entry point: check circuit breaker, fetch raw data,
        persist via upsert, update system status.
        """
        if self._check_circuit_breaker():
            return []

        try:
            results = await self._fetch_raw()
        except Exception as exc:
            logger.error(f"{self.source_name} fetch failed: {exc}")
            self._update_system_status(error=str(exc))
            return []

        if not results:
            self._update_system_status()
            return results

        logger.info(f"{self.source_name}: {len(results)} rows across all categories")

        # Persist to database
        try:
            db = SessionLocal()
            try:
                seen_markets: set[str] = set()

                for r in results:
                    self._upsert_price(db, r)

                    mid = r["market_id"]
                    if mid not in seen_markets:
                        seen_markets.add(mid)
                        self._upsert_tracked_market(
                            db, mid, r.get("title", ""), r.get("category", "other")
                        )

                db.commit()
                logger.info(f"Saved {len(results)} {self.source_name} prices to database")
            finally:
                db.close()
        except Exception as exc:
            logger.error(f"Failed to save {self.source_name} data to DB: {exc}")
            self._update_system_status(error=str(exc))
            return results

        self._update_system_status()
        return results
