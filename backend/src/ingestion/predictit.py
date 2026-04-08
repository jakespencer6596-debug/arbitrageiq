"""
PredictIt prediction-market ingestion client.

Fetches the entire PredictIt market catalogue in a single API call,
parses ``lastTradePrice`` from every contract as the implied probability,
and persists snapshots to the MarketPrice and TrackedMarket tables.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import httpx
import logging
from datetime import datetime, timezone

from constants import PREDICTIT_API_URL
import constants
from db.models import SessionLocal, MarketPrice, TrackedMarket, SystemStatus
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)


class PredictItClient:
    """
    Async client for the PredictIt marketdata endpoint.

    The PredictIt API exposes a single endpoint that returns every market
    and its contracts in one response.  This client parses the response,
    normalises contract prices into implied probabilities, and writes them
    to the database.
    """

    def __init__(self) -> None:
        """Initialise with the PredictIt API URL from constants."""
        self.url = PREDICTIT_API_URL

    def _update_system_status(self, error: str | None = None) -> None:
        """
        Persist PredictIt ingestor health information to SystemStatus.

        Args:
            error: If not None, the error message to record.
        """
        try:
            db = SessionLocal()
            try:
                status = (
                    db.query(SystemStatus)
                    .filter(SystemStatus.source == "predictit")
                    .first()
                )
                if not status:
                    status = SystemStatus(source="predictit", component="predictit")
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
                f"Could not update SystemStatus for predictit: {exc}"
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
        left untouched.  Otherwise a new active TrackedMarket is created.

        Args:
            db: An active SQLAlchemy session.
            market_id: The PredictIt market or contract identifier.
            title: Human-readable market name.
            category: Classified category string.
        """
        existing = (
            db.query(TrackedMarket)
            .filter(
                TrackedMarket.source == "predictit",
                TrackedMarket.market_id == market_id,
            )
            .first()
        )
        if not existing:
            db.add(
                TrackedMarket(
                    source="predictit",
                    market_id=market_id,
                    event_name=title,
                    market_title=title,
                    category=category,
                    is_active=True,
                )
            )

    async def fetch(self) -> list[dict]:
        """
        Fetch all PredictIt markets and return normalised contract rows.

        The endpoint ``/api/marketdata/all/`` returns every market with
        nested ``contracts``.  For each contract:

        1. ``lastTradePrice`` is treated directly as the implied YES
           probability (PredictIt prices are on a 0.00--1.00 scale).
        2. NO probability is computed as ``1 - lastTradePrice``.
        3. A MarketPrice row is written.
        4. Each market is auto-tracked via TrackedMarket upsert.

        Returns:
            A list of dicts with keys: source, market_id, contract_id,
            market_name, contract_name, yes_price, no_price, category,
            timestamp.
        """
        results: list[dict] = []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(self.url)
                resp.raise_for_status()
                data = resp.json()

            markets = data.get("markets", [])
            logger.info(
                f"PredictIt returned {len(markets)} markets"
            )

            for market in markets:
                market_id = str(market.get("id", ""))
                market_name = market.get("name", "") or market.get(
                    "shortName", ""
                )
                market_url = market.get("url", "")
                category = categorise(market_name)

                contracts = market.get("contracts", [])

                for contract in contracts:
                    contract_id = str(contract.get("id", ""))
                    contract_name = contract.get("name", "") or contract.get(
                        "shortName", ""
                    )

                    last_trade = contract.get("lastTradePrice")
                    if last_trade is None:
                        # Fall back to bestBuyYesCost or bestSellYesCost
                        last_trade = contract.get("bestBuyYesCost")
                    if last_trade is None:
                        continue

                    try:
                        yes_price = float(last_trade)
                    except (ValueError, TypeError):
                        continue

                    # Clamp to [0, 1] -- PredictIt prices should already be
                    # in this range but defensive coding never hurts
                    yes_price = max(0.0, min(1.0, yes_price))
                    no_price = 1.0 - yes_price

                    best_buy_yes = contract.get("bestBuyYesCost")
                    best_buy_no = contract.get("bestBuyNoCost")
                    best_sell_yes = contract.get("bestSellYesCost")
                    best_sell_no = contract.get("bestSellNoCost")

                    results.append(
                        {
                            "source": "predictit",
                            "market_id": market_id,
                            "contract_id": contract_id,
                            "market_name": market_name,
                            "contract_name": contract_name,
                            "yes_price": yes_price,
                            "no_price": no_price,
                            "category": category,
                            "timestamp": datetime.now(timezone.utc),
                            "raw": {
                                "market_url": market_url,
                                "bestBuyYesCost": best_buy_yes,
                                "bestBuyNoCost": best_buy_no,
                                "bestSellYesCost": best_sell_yes,
                                "bestSellNoCost": best_sell_no,
                                "lastTradePrice": float(last_trade),
                            },
                        }
                    )

        except Exception as exc:
            logger.error(f"PredictIt fetch failed: {exc}")
            self._update_system_status(error=str(exc))
            return results

        logger.info(f"PredictIt: {len(results)} rows across all categories")

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
                    composite_id = f"{r['market_id']}_{r['contract_id']}"
                    title = f"{r['market_name']} -- {r['contract_name']}"

                    # Upsert
                    existing = (
                        db.query(MarketPrice)
                        .filter(
                            MarketPrice.source == "predictit",
                            MarketPrice.market_id == composite_id,
                            MarketPrice.outcome == "yes",
                        )
                        .first()
                    )
                    if existing:
                        existing.implied_probability = r["yes_price"]
                        existing.yes_price = r["yes_price"]
                        existing.no_price = r["no_price"]
                        existing.last_traded_price = r["yes_price"]
                        existing.fetched_at = r["timestamp"]
                        existing.timestamp = r["timestamp"]
                        existing.is_active = True
                        existing.event_name = title
                        existing.category = r["category"]
                    else:
                        db.add(
                            MarketPrice(
                                source="predictit",
                                market_id=composite_id,
                                event_name=title,
                                market_title=title,
                                outcome="yes",
                                implied_probability=r["yes_price"],
                                category=r["category"],
                                yes_price=r["yes_price"],
                                no_price=r["no_price"],
                                last_traded_price=r["yes_price"],
                                raw_payload=r.get("raw"),
                                fetched_at=r["timestamp"],
                            )
                        )

                    mid = r["market_id"]
                    if mid not in seen_markets:
                        seen_markets.add(mid)
                        self._upsert_tracked_market(
                            db, mid, r["market_name"], r["category"]
                        )

                db.commit()
                logger.info(
                    f"Saved {len(results)} PredictIt prices to database"
                )
            finally:
                db.close()
        except Exception as exc:
            logger.error(f"Failed to save PredictIt data to DB: {exc}")
            self._update_system_status(error=str(exc))
            return results

        self._update_system_status()
        return results
