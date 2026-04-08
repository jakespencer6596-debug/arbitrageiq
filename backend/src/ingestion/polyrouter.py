"""
PolyRouter unified prediction market ingestion client.

Fetches data from PolyRouter (polyrouter.io) — a single API that aggregates
7 prediction market platforms: Polymarket, Kalshi, Manifold, Limitless,
ProphetX, Novig, and SX.bet.

Free during open beta. No authentication required.
We skip platforms we already ingest directly and focus on the new ones:
Limitless, ProphetX, Novig.
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

POLYROUTER_BASE = "https://api-v2.polyrouter.io"
POLYROUTER_API_KEY = os.getenv("POLYROUTER_API_KEY", "")

# Platforms we already ingest directly — skip these from PolyRouter
SKIP_PLATFORMS = {"polymarket", "kalshi", "manifold", "sxbet", "sx.bet", "sx bet"}

# Platforms we want from PolyRouter (new data)
WANT_PLATFORMS = {"limitless", "prophetx", "novig"}


class PolyRouterClient(BaseClient):
    """
    Fetches prediction market data from PolyRouter's unified API.
    Focuses on platforms not already directly integrated.
    """

    source_name = "polyrouter"

    async def _fetch_raw(self) -> list[dict]:
        if not POLYROUTER_API_KEY:
            logger.info("PolyRouter: no API key configured (set POLYROUTER_API_KEY) — skipping")
            return []

        results: list[dict] = []

        async with httpx.AsyncClient(timeout=30) as client:
            try:
                # PolyRouter v2 API: GET /markets
                resp = await client.get(
                    f"{POLYROUTER_BASE}/markets",
                    headers={"X-API-Key": POLYROUTER_API_KEY},
                    params={"limit": 500},
                )
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    markets = data
                elif isinstance(data, dict):
                    markets = data.get("data", data.get("markets", []))
                else:
                    markets = []

                logger.info(f"PolyRouter: received {len(markets)} markets")
            except Exception as exc:
                logger.error(f"PolyRouter fetch failed: {exc}")
                raise

            for mkt in markets:
                # Determine which platform this market is from
                platform = (
                    mkt.get("platform", "")
                    or mkt.get("source", "")
                    or mkt.get("exchange", "")
                ).lower()

                # Skip platforms we already ingest directly
                if platform in SKIP_PLATFORMS:
                    continue

                market_id = str(
                    mkt.get("id", "")
                    or mkt.get("marketId", "")
                    or mkt.get("market_id", "")
                )
                title = (
                    mkt.get("title", "")
                    or mkt.get("question", "")
                    or mkt.get("name", "")
                )
                if not market_id or not title:
                    continue

                # Extract probability
                yes_price = None
                for field in ["probability", "yesPrice", "yes_price", "lastPrice", "price"]:
                    val = mkt.get(field)
                    if val is not None:
                        try:
                            yes_price = float(val)
                            break
                        except (ValueError, TypeError):
                            continue

                if yes_price is None or yes_price <= 0 or yes_price >= 1:
                    continue

                no_price = round(1.0 - yes_price, 4)
                category = categorise(title)
                volume = mkt.get("volume", 0) or 0

                # Use platform-specific source name for arb detection
                source = f"pr_{platform}" if platform else "polyrouter"

                results.append({
                    "source": source,
                    "market_id": market_id,
                    "title": title,
                    "outcome": "yes",
                    "yes_price": round(yes_price, 4),
                    "no_price": no_price,
                    "category": category,
                    "volume": volume,
                    "timestamp": datetime.now(timezone.utc),
                    "metadata": {
                        "platform": platform,
                        "url": mkt.get("url", ""),
                    },
                })

        return results
