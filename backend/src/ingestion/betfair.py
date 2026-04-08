"""
Betfair Exchange ingestion client.

Fetches market data from the Betfair Exchange — the world's largest
betting exchange. Uses the free delayed API key which provides price
snapshots with 1-180 second delay.

Requires a Betfair account and delayed app key (free to obtain).
Set BETFAIR_APP_KEY and BETFAIR_SESSION_TOKEN in env.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import httpx
import logging
from datetime import datetime, timezone, timedelta

from ingestion.base import BaseClient
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)

BETFAIR_BASE = "https://api.betfair.com/exchange/betting/rest/v1.0"
BETFAIR_APP_KEY = os.getenv("BETFAIR_APP_KEY", "")
BETFAIR_SESSION_TOKEN = os.getenv("BETFAIR_SESSION_TOKEN", "")

# Betfair event type IDs for key categories
EVENT_TYPE_IDS = {
    "soccer": "1",
    "tennis": "2",
    "golf": "3",
    "cricket": "4",
    "rugby_union": "5",
    "boxing": "6",
    "horse_racing": "7",
    "motor_sport": "8",
    "politics": "2378961",
    "basketball": "7522",
    "american_football": "6423",
    "baseball": "7511",
    "ice_hockey": "7524",
    "mma": "26420387",
}


class BetfairClient(BaseClient):
    """
    Fetches exchange odds from Betfair's delayed API.
    Covers sports and politics with full orderbook depth.
    """

    source_name = "betfair"
    circuit_breaker_threshold = 5

    async def _betfair_request(self, client: httpx.AsyncClient, endpoint: str, payload: dict) -> dict:
        """Make authenticated request to Betfair API."""
        resp = await client.post(
            f"{BETFAIR_BASE}/{endpoint}/",
            json={"filter": payload} if "filter" not in payload else payload,
            headers={
                "X-Application": BETFAIR_APP_KEY,
                "X-Authentication": BETFAIR_SESSION_TOKEN,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def _fetch_raw(self) -> list[dict]:
        if not BETFAIR_APP_KEY or not BETFAIR_SESSION_TOKEN:
            logger.info("Betfair: no app key/session configured — skipping")
            return []

        results: list[dict] = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch events from key categories
            categories_to_fetch = ["politics", "soccer", "basketball", "tennis", "american_football"]

            for cat_name in categories_to_fetch:
                event_type_id = EVENT_TYPE_IDS.get(cat_name)
                if not event_type_id:
                    continue

                try:
                    # List markets for this event type
                    market_filter = {
                        "filter": {
                            "eventTypeIds": [event_type_id],
                            "marketStartTime": {
                                "from": datetime.now(timezone.utc).isoformat(),
                                "to": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                            },
                            "inPlayOnly": False,
                        },
                        "maxResults": 50,
                        "marketProjection": ["RUNNER_METADATA", "EVENT"],
                    }

                    markets = await self._betfair_request(client, "listMarketCatalogue", market_filter)

                    if not isinstance(markets, list):
                        continue

                    # Get prices for each market (batch)
                    market_ids = [m.get("marketId") for m in markets if m.get("marketId")]
                    if not market_ids:
                        continue

                    # Batch price request (max 40 per call)
                    for batch_start in range(0, len(market_ids), 40):
                        batch_ids = market_ids[batch_start:batch_start + 40]

                        price_data = await self._betfair_request(
                            client,
                            "listMarketBook",
                            {
                                "marketIds": batch_ids,
                                "priceProjection": {
                                    "priceData": ["EX_BEST_OFFERS"],
                                },
                            },
                        )

                        if not isinstance(price_data, list):
                            continue

                        # Build market_id -> catalogue lookup
                        catalogue_map = {m["marketId"]: m for m in markets if m.get("marketId") in batch_ids}

                        for book in price_data:
                            market_id = book.get("marketId", "")
                            cat_entry = catalogue_map.get(market_id, {})
                            event = cat_entry.get("event", {})
                            event_name = event.get("name", "")
                            market_name = cat_entry.get("marketName", "")

                            full_name = f"{event_name}: {market_name}" if event_name else market_name
                            if not full_name:
                                continue

                            category = "politics" if cat_name == "politics" else "sports"

                            runners = book.get("runners", [])
                            runner_catalogue = cat_entry.get("runners", [])
                            runner_names = {
                                str(r.get("selectionId")): r.get("runnerName", "")
                                for r in runner_catalogue
                            }

                            for runner in runners:
                                selection_id = str(runner.get("selectionId", ""))
                                runner_name = runner_names.get(selection_id, f"Runner {selection_id}")

                                # Get best back price (probability)
                                back_prices = runner.get("ex", {}).get("availableToBack", [])
                                lay_prices = runner.get("ex", {}).get("availableToLay", [])

                                if not back_prices and not lay_prices:
                                    continue

                                best_back = back_prices[0].get("price", 0) if back_prices else 0
                                best_lay = lay_prices[0].get("price", 0) if lay_prices else 0

                                # Convert decimal odds to implied probability
                                if best_back > 1:
                                    implied_prob = 1.0 / best_back
                                elif best_lay > 1:
                                    implied_prob = 1.0 / best_lay
                                else:
                                    continue

                                if implied_prob <= 0.01 or implied_prob >= 0.99:
                                    continue

                                results.append({
                                    "source": "betfair",
                                    "market_id": f"{market_id}_{selection_id}",
                                    "title": f"{full_name}: {runner_name}",
                                    "outcome": "yes",
                                    "yes_price": round(implied_prob, 4),
                                    "no_price": round(1.0 - implied_prob, 4),
                                    "raw_odds": best_back if best_back > 1 else best_lay,
                                    "category": category,
                                    "volume": 0,
                                    "timestamp": datetime.now(timezone.utc),
                                    "metadata": {
                                        "back": best_back,
                                        "lay": best_lay,
                                        "runner": runner_name,
                                    },
                                })

                except Exception as exc:
                    logger.debug(f"Betfair: failed to fetch {cat_name}: {exc}")
                    continue

        return results
