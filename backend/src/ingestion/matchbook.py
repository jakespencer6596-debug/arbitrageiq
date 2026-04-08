"""
Matchbook Exchange ingestion client.

Fetches exchange data from Matchbook (matchbook.com).
Free under 1,000,000 GET requests/month. No API key needed for reads.
Covers major sports with ~2% commission.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import httpx
import logging
from datetime import datetime, timezone

from ingestion.base import BaseClient
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)

MATCHBOOK_BASE = "https://api.matchbook.com/edge/rest"
MATCHBOOK_USER = os.getenv("MATCHBOOK_USER", "")
MATCHBOOK_PASS = os.getenv("MATCHBOOK_PASS", "")

# Matchbook sport IDs
SPORT_IDS = {
    "soccer": 15,
    "basketball": 10,
    "american_football": 9,
    "tennis": 24,
    "baseball": 1,
    "ice_hockey": 11,
    "boxing": 6,
    "mma": 30,
    "politics": 1000093,
}


class MatchbookClient(BaseClient):
    """
    Fetches exchange odds from Matchbook.
    Free REST API with session-based auth (anonymous reads supported).
    """

    source_name = "matchbook"

    async def _login(self, client: httpx.AsyncClient) -> str | None:
        """Get session token from Matchbook."""
        if not MATCHBOOK_USER or not MATCHBOOK_PASS:
            return None
        try:
            resp = await client.post(
                "https://api.matchbook.com/bpapi/rest/security/session",
                json={"username": MATCHBOOK_USER, "password": MATCHBOOK_PASS},
            )
            if resp.status_code == 200:
                return resp.json().get("session-token")
        except Exception:
            pass
        return None

    async def _fetch_raw(self) -> list[dict]:
        if not MATCHBOOK_USER:
            logger.info("Matchbook: no credentials configured (set MATCHBOOK_USER, MATCHBOOK_PASS) — skipping")
            return []

        results: list[dict] = []

        async with httpx.AsyncClient(timeout=20) as client:
            session_token = await self._login(client)
            if not session_token:
                logger.warning("Matchbook: login failed — skipping")
                return []
            client.headers["session-token"] = session_token
            for cat_name, sport_id in SPORT_IDS.items():
                try:
                    resp = await client.get(
                        f"{MATCHBOOK_BASE}/events",
                        params={
                            "sport-ids": sport_id,
                            "states": "open",
                            "per-page": 50,
                            "offset": 0,
                            "include-prices": "true",
                            "price-depth": 1,
                        },
                    )
                    if resp.status_code != 200:
                        logger.debug(f"Matchbook: {cat_name} returned {resp.status_code}")
                        continue

                    data = resp.json()
                    events = data.get("events", [])
                    logger.info(f"Matchbook: {len(events)} events for {cat_name}")

                    for event in events:
                        event_name = event.get("name", "")

                        for market in event.get("markets", []):
                            market_id = str(market.get("id", ""))
                            market_name = market.get("name", "")

                            for runner in market.get("runners", []):
                                runner_name = runner.get("name", "")
                                runner_id = str(runner.get("id", ""))

                                prices = runner.get("prices", [])
                                back_prices = [p for p in prices if p.get("side") == "back"]
                                lay_prices = [p for p in prices if p.get("side") == "lay"]

                                best_back = back_prices[0].get("decimal-odds", 0) if back_prices else 0
                                best_lay = lay_prices[0].get("decimal-odds", 0) if lay_prices else 0

                                if best_back > 1:
                                    implied_prob = 1.0 / best_back
                                elif best_lay > 1:
                                    implied_prob = 1.0 / best_lay
                                else:
                                    continue

                                if implied_prob <= 0.01 or implied_prob >= 0.99:
                                    continue

                                full_name = f"{event_name}: {runner_name}"
                                category = "politics" if cat_name == "politics" else "sports"

                                results.append({
                                    "source": "matchbook",
                                    "market_id": f"{market_id}_{runner_id}",
                                    "title": full_name,
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
                                    },
                                })

                except Exception as exc:
                    logger.debug(f"Matchbook: failed to fetch {cat_name}: {exc}")
                    continue

        return results
