"""
Smarkets betting exchange ingestion client.

Fetches real-money prediction market data from Smarkets (UK exchange).
Covers politics, sports, and entertainment with full bid/ask orderbook.
No authentication required for read access.
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

SMARKETS_BASE = "https://api.smarkets.com/v3"

# Parent event IDs for political markets on Smarkets
POLITICAL_PARENT_IDS = [
    924650,    # USA
    924651,    # Europe
    121012,    # UK
    148128,    # Ireland
    784698,    # Donald Trump
    44136685,  # 2028 Presidential Election
    44276743,  # 2026 Midterms
]

# Sport parent IDs
SPORTS_PARENT_IDS = []  # Will discover dynamically

CATEGORY_OVERRIDES = {
    "politics": POLITICAL_PARENT_IDS,
}


class SmarketsClient:
    """Fetches prediction market data from Smarkets exchange."""

    def __init__(self):
        self.base_url = SMARKETS_BASE

    def _update_system_status(self, error: str | None = None) -> None:
        try:
            db = SessionLocal()
            try:
                status = db.query(SystemStatus).filter(SystemStatus.source == "smarkets").first()
                if not status:
                    status = SystemStatus(source="smarkets", component="smarkets")
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
            logger.debug(f"Could not update SystemStatus for smarkets: {exc}")

    async def _get_child_events(self, client: httpx.AsyncClient, parent_id: int) -> list[dict]:
        """Get child events under a parent category."""
        try:
            resp = await client.get(
                f"{self.base_url}/events/",
                params={"parent_id": parent_id, "state": "upcoming", "limit": 50},
            )
            if resp.status_code == 200:
                return resp.json().get("events", [])
        except Exception:
            pass
        return []

    async def _get_markets_and_quotes(self, client: httpx.AsyncClient, event_id: int, event_name: str) -> list[dict]:
        """Get markets, contracts, and live quotes for an event."""
        results = []
        try:
            # Get markets for this event
            resp = await client.get(f"{self.base_url}/events/{event_id}/markets/")
            if resp.status_code != 200:
                return []
            markets = resp.json().get("markets", [])

            for market in markets[:5]:  # Limit to 5 markets per event
                market_id = market.get("id")
                market_name = market.get("name", "")

                # Get contracts
                resp2 = await client.get(f"{self.base_url}/markets/{market_id}/contracts/")
                if resp2.status_code != 200:
                    continue
                contracts = resp2.json().get("contracts", [])

                # Get quotes (bid/ask)
                resp3 = await client.get(f"{self.base_url}/markets/{market_id}/quotes/")
                if resp3.status_code != 200:
                    continue
                quotes = resp3.json()

                for contract in contracts:
                    contract_id = str(contract.get("id", ""))
                    contract_name = contract.get("name", "")
                    q = quotes.get(contract_id, {})
                    bids = q.get("bids", [])
                    offers = q.get("offers", [])

                    # Smarkets prices are in basis points (0-10000 = 0-100%)
                    best_bid = bids[0].get("price", 0) / 10000 if bids else 0
                    best_ask = offers[0].get("price", 0) / 10000 if offers else 0

                    if best_bid <= 0 and best_ask <= 0:
                        continue

                    # Use midpoint as implied probability
                    mid = (best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else max(best_bid, best_ask)
                    if mid <= 0.01 or mid >= 0.99:
                        continue

                    full_name = f"{event_name}: {contract_name}" if event_name != market_name else f"{market_name}: {contract_name}"
                    category = categorise(full_name)

                    # Override: if we fetched from political parent IDs, force politics
                    if constants.ACTIVE_CATEGORY == "politics":
                        category = "politics"

                    results.append({
                        "source": "smarkets",
                        "market_id": f"{market_id}_{contract_id}",
                        "title": full_name,
                        "outcome": "yes",
                        "yes_price": round(mid, 4),
                        "no_price": round(1.0 - mid, 4),
                        "bid": round(best_bid, 4),
                        "ask": round(best_ask, 4),
                        "category": category,
                        "volume": 0,
                        "timestamp": datetime.now(timezone.utc),
                        "url": f"https://smarkets.com/event/{event_id}",
                    })
        except Exception as exc:
            logger.debug(f"Smarkets market fetch error for event {event_id}: {exc}")

        return results

    async def fetch(self) -> list[dict]:
        """Fetch political prediction market data from Smarkets."""
        if constants.ACTIVE_CATEGORY is None:
            logger.info("Smarkets: no active category — skipping")
            return []

        results: list[dict] = []

        try:
            async with httpx.AsyncClient(timeout=20) as client:
                # Get events based on category
                parent_ids = CATEGORY_OVERRIDES.get(constants.ACTIVE_CATEGORY, POLITICAL_PARENT_IDS)

                for parent_id in parent_ids:
                    # Get child events
                    child_events = await self._get_child_events(client, parent_id)

                    for event in child_events:
                        event_id = event.get("id")
                        event_name = event.get("name", "")

                        # Get markets + quotes for this event
                        event_results = await self._get_markets_and_quotes(client, event_id, event_name)
                        results.extend(event_results)

                        # Also check sub-events (Smarkets uses nested hierarchy)
                        sub_events = await self._get_child_events(client, event_id)
                        for sub in sub_events:
                            sub_results = await self._get_markets_and_quotes(
                                client, sub.get("id"), sub.get("name", event_name)
                            )
                            results.extend(sub_results)

            logger.info(f"Smarkets: fetched {len(results)} contract prices")

        except Exception as exc:
            logger.error(f"Smarkets fetch failed: {exc}")
            self._update_system_status(error=str(exc))
            return results

        # Filter to active category
        results = [r for r in results if r["category"] == constants.ACTIVE_CATEGORY]
        logger.info(f"Smarkets: {len(results)} rows match active category '{constants.ACTIVE_CATEGORY}'")

        if not results:
            self._update_system_status()
            return results

        # Persist to database
        try:
            db = SessionLocal()
            try:
                db.query(MarketPrice).filter(
                    MarketPrice.source == "smarkets",
                    MarketPrice.is_active == True,
                ).update({"is_active": False})

                for r in results:
                    db.add(MarketPrice(
                        source="smarkets",
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
                        metadata_={"url": r["url"], "bid": r["bid"], "ask": r["ask"]},
                    ))

                db.commit()
                logger.info(f"Saved {len(results)} Smarkets prices to database")
            finally:
                db.close()
        except Exception as exc:
            logger.error(f"Failed to save Smarkets data to DB: {exc}")
            self._update_system_status(error=str(exc))
            return results

        self._update_system_status()
        return results
