"""
Cloudbet crypto sportsbook ingestion client.

Fetches odds from Cloudbet's public Feed API.
Free affiliate API key available. GraphQL-based.
Covers sports, esports, and crypto betting markets.
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

CLOUDBET_BASE = "https://sports-api.cloudbet.com/pub/v2/odds"
CLOUDBET_API_KEY = os.getenv("CLOUDBET_API_KEY", "")

# Cloudbet sport keys
SPORT_KEYS = [
    "soccer",
    "basketball",
    "tennis",
    "american-football",
    "baseball",
    "ice-hockey",
    "mma",
    "boxing",
    "esports",
    "politics",
]


class CloudbetClient(BaseClient):
    """
    Fetches odds from Cloudbet's public sports API.
    Crypto-native sportsbook with free feed API.
    """

    source_name = "cloudbet"

    async def _fetch_raw(self) -> list[dict]:
        if not CLOUDBET_API_KEY:
            logger.info("Cloudbet: no API key configured (set CLOUDBET_API_KEY) — skipping")
            return []

        results: list[dict] = []

        headers = {
            "X-API-Key": CLOUDBET_API_KEY,
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            for sport_key in SPORT_KEYS:
                try:
                    # Cloudbet v2: GET /odds/sports/{key} or /odds/competitions/{key}
                    resp = await client.get(
                        f"{CLOUDBET_BASE}/sports/{sport_key}",
                    )
                    if resp.status_code != 200:
                        resp = await client.get(
                            f"{CLOUDBET_BASE}/competitions/{sport_key}",
                        )
                        if resp.status_code != 200:
                            continue

                    data = resp.json()

                    # Navigate response structure (may vary by endpoint)
                    competitions = data.get("competitions", [])
                    if not competitions and isinstance(data, list):
                        competitions = data

                    for comp in competitions:
                        events = comp.get("events", [])
                        if not events and isinstance(comp, dict):
                            events = [comp]  # Single event response

                        for event in events:
                            event_name = event.get("name", "")
                            home = event.get("home", {}).get("name", "")
                            away = event.get("away", {}).get("name", "")
                            if home and away:
                                event_name = f"{away} vs {home}"
                            if not event_name:
                                continue

                            event_id = str(event.get("id", ""))
                            category = "politics" if sport_key == "politics" else "sports"

                            # Extract markets
                            markets = event.get("markets", {})
                            if isinstance(markets, list):
                                markets = {str(i): m for i, m in enumerate(markets)}

                            for market_key, market in markets.items():
                                if not isinstance(market, dict):
                                    continue

                                selections = market.get("selections", [])
                                if isinstance(selections, dict):
                                    selections = list(selections.values())

                                for sel in selections:
                                    if not isinstance(sel, dict):
                                        continue

                                    outcome_name = sel.get("name", "") or sel.get("outcome", "")
                                    price = sel.get("price")
                                    if price is None:
                                        continue

                                    try:
                                        decimal_odds = float(price)
                                    except (ValueError, TypeError):
                                        continue

                                    if decimal_odds <= 1:
                                        continue

                                    implied_prob = 1.0 / decimal_odds
                                    if implied_prob <= 0.01 or implied_prob >= 0.99:
                                        continue

                                    full_name = f"{event_name}: {outcome_name}" if outcome_name else event_name

                                    results.append({
                                        "source": "cloudbet",
                                        "market_id": f"{event_id}_{market_key}_{outcome_name}",
                                        "title": full_name,
                                        "outcome": "yes",
                                        "yes_price": round(implied_prob, 4),
                                        "no_price": round(1.0 - implied_prob, 4),
                                        "raw_odds": decimal_odds,
                                        "category": category,
                                        "volume": 0,
                                        "timestamp": datetime.now(timezone.utc),
                                    })

                except Exception as exc:
                    logger.debug(f"Cloudbet: failed to fetch {sport_key}: {exc}")
                    continue

        return results
