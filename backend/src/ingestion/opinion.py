"""
Opinion prediction market ingestion client.

Fetches data from Opinion (opinion.xyz) — the 3rd largest prediction market.
Built on BNB Chain with a CLOB-based orderbook.
Free API, no authentication required for market data reads.
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

OPINION_BASE = "https://openapi.opinion.trade"
OPINION_API_KEY = os.getenv("OPINION_API_KEY", "")


class OpinionClient(BaseClient):
    """
    Fetches prediction market data from Opinion.
    Covers macro events, crypto, politics, culture, geopolitics.
    """

    source_name = "opinion"

    async def _fetch_raw(self) -> list[dict]:
        if not OPINION_API_KEY:
            logger.info("Opinion: no API key configured (set OPINION_API_KEY) — skipping")
            return []

        results: list[dict] = []

        async with httpx.AsyncClient(timeout=20) as client:
            try:
                # Opinion Open API: GET /openapi/market
                resp = await client.get(
                    f"{OPINION_BASE}/openapi/market",
                    headers={"apikey": OPINION_API_KEY},
                    params={"page": 1, "pageSize": 200},
                )
                resp.raise_for_status()
                data = resp.json()

                # Response format: {"code": 0, "msg": "success", "result": {...}}
                result = data.get("result", data)
                if isinstance(result, dict):
                    markets = result.get("data", result.get("markets", result.get("list", [])))
                elif isinstance(result, list):
                    markets = result
                else:
                    markets = []

                logger.info(f"Opinion: received {len(markets)} markets")
            except Exception as exc:
                logger.error(f"Opinion fetch failed: {exc}")
                raise

            for mkt in markets:
                # Adapt to whatever field names Opinion uses
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
                for field in ["yesPrice", "yes_price", "probability", "lastPrice", "last_price"]:
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
                volume = mkt.get("volume", 0) or mkt.get("totalVolume", 0) or 0

                results.append({
                    "source": "opinion",
                    "market_id": market_id,
                    "title": title,
                    "outcome": "yes",
                    "yes_price": round(yes_price, 4),
                    "no_price": no_price,
                    "category": category,
                    "volume": volume,
                    "timestamp": datetime.now(timezone.utc),
                    "metadata": {"url": mkt.get("url", "")},
                })

        return results
