"""
SX Bet decentralized exchange ingestion client.

Fetches prediction market data from SX Bet (api.sx.bet).
Covers politics, crypto, economics, entertainment on SX Network.
No authentication required.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import httpx
import logging
from datetime import datetime, timezone

import constants
from db.models import SessionLocal, MarketPrice, SystemStatus
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)

SXBET_BASE = "https://api.sx.bet"

# SX Bet sport IDs that map to prediction market categories
SPORT_ID_MAP = {
    "politics": 17,
    "crypto": 14,
    "entertainment": 18,
    "other": 16,  # economics
}


class SXBetClient:
    """Fetches prediction market data from SX Bet decentralized exchange."""

    def _update_system_status(self, error: str | None = None) -> None:
        try:
            db = SessionLocal()
            try:
                status = db.query(SystemStatus).filter(SystemStatus.source == "sxbet").first()
                if not status:
                    status = SystemStatus(source="sxbet", component="sxbet")
                    db.add(status)
                now = datetime.now(timezone.utc)
                if error:
                    status.status = "degraded"
                    status.last_failure_at = now
                    status.last_error = error
                    status.consecutive_failures = (status.consecutive_failures or 0) + 1
                else:
                    status.status = "healthy"
                    status.last_success_at = now
                    status.consecutive_failures = 0
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.debug(f"Could not update SystemStatus for sxbet: {exc}")

    async def fetch(self) -> list[dict]:
        """Fetch active markets from SX Bet."""
        if constants.ACTIVE_CATEGORY is None:
            logger.info("SX Bet: no active category — skipping")
            return []

        # Circuit breaker: if 10+ consecutive failures, skip
        try:
            db = SessionLocal()
            status = db.query(SystemStatus).filter(SystemStatus.source == "sxbet").first()
            if status and (status.consecutive_failures or 0) >= 10:
                logger.debug("SX Bet: circuit breaker active, skipping")
                # Reset after 1 hour
                if status.last_failure_at:
                    from datetime import timedelta
                    if datetime.now(timezone.utc) - status.last_failure_at.replace(tzinfo=timezone.utc) > timedelta(hours=1):
                        status.consecutive_failures = 0
                        db.commit()
                        logger.info("SX Bet: circuit breaker reset after 1 hour")
                    else:
                        db.close()
                        return []
                else:
                    db.close()
                    return []
            db.close()
        except Exception:
            pass

        # Get sport ID for active category
        sport_id = SPORT_ID_MAP.get(constants.ACTIVE_CATEGORY)
        if sport_id is None:
            logger.debug(f"SX Bet: no sport ID for category '{constants.ACTIVE_CATEGORY}' — skipping")
            return []

        results: list[dict] = []

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(
                    f"{SXBET_BASE}/markets/active",
                    params={"sportId": sport_id, "pageSize": 100},
                )
                resp.raise_for_status()
                data = resp.json()

                markets = data.get("data", [])
                logger.info(f"SX Bet: received {len(markets)} markets for sport {sport_id}")

                for mkt in markets:
                    market_hash = mkt.get("marketHash", "")
                    title = mkt.get("title", "") or mkt.get("teamOneName", "")
                    outcome1 = mkt.get("teamOneName", "Yes")
                    outcome2 = mkt.get("teamTwoName", "No")

                    # SX Bet uses implied odds format
                    line = mkt.get("line")
                    spread = mkt.get("spread")

                    if not title or not market_hash:
                        continue

                    category = categorise(title)
                    if category != constants.ACTIVE_CATEGORY:
                        continue

                    # Try to get best prices from orderbook
                    try:
                        order_resp = await client.get(
                            f"{SXBET_BASE}/orders",
                            params={"marketHash": market_hash, "pageSize": 10},
                        )
                        if order_resp.status_code == 200:
                            orders = order_resp.json().get("data", [])
                            # Extract best bid/ask
                            bids = [o for o in orders if o.get("isMakerBettingOutcomeOne") == True]
                            asks = [o for o in orders if o.get("isMakerBettingOutcomeOne") == False]

                            if bids or asks:
                                best_bid_price = max((float(o.get("impliedOdds", 0)) for o in bids), default=0)
                                best_ask_price = min((float(o.get("impliedOdds", 1)) for o in asks), default=1)
                                mid = (best_bid_price + best_ask_price) / 2 if best_bid_price > 0 else best_ask_price

                                if 0.01 < mid < 0.99:
                                    results.append({
                                        "source": "sxbet",
                                        "market_id": market_hash[:32],
                                        "title": f"{title}: {outcome1}",
                                        "outcome": "yes",
                                        "yes_price": round(mid, 4),
                                        "no_price": round(1.0 - mid, 4),
                                        "category": category,
                                        "volume": 0,
                                        "timestamp": datetime.now(timezone.utc),
                                    })
                    except Exception:
                        pass

        except Exception as exc:
            logger.error(f"SX Bet fetch failed: {exc}")
            self._update_system_status(error=str(exc))
            return results

        logger.info(f"SX Bet: {len(results)} rows match active category")

        if not results:
            self._update_system_status()
            return results

        # Persist
        try:
            db = SessionLocal()
            try:
                db.query(MarketPrice).filter(
                    MarketPrice.source == "sxbet",
                    MarketPrice.is_active == True,
                ).update({"is_active": False})

                for r in results:
                    db.add(MarketPrice(
                        source="sxbet",
                        market_id=r["market_id"],
                        event_name=r["title"],
                        market_title=r["title"],
                        outcome=r["outcome"],
                        implied_probability=r["yes_price"],
                        category=r["category"],
                        yes_price=r["yes_price"],
                        no_price=r["no_price"],
                        volume=r.get("volume"),
                        raw_payload=None,
                        fetched_at=r["timestamp"],
                    ))

                db.commit()
                logger.info(f"Saved {len(results)} SX Bet prices to database")
            finally:
                db.close()
        except Exception as exc:
            logger.error(f"Failed to save SX Bet data to DB: {exc}")
            self._update_system_status(error=str(exc))

        self._update_system_status()
        return results
