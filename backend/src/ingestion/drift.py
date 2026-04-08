"""
Drift Protocol BET prediction market ingestion client.

Drift (drift.trade) is a Solana-based trading platform with prediction
markets (BET). Real money (30+ tokens), free API via their HTTP gateway.
"""

import httpx
import logging
from datetime import datetime, timezone

from ingestion.base import BaseClient
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)

# Drift public API — no auth for market data reads
DRIFT_API_BASE = "https://drift-historical-data-v2.s3.eu-west-1.amazonaws.com"
DRIFT_GATEWAY = "https://mainnet-beta.api.drift.trade"
_MAX_MARKETS = 100


class DriftClient(BaseClient):
    source_name = "drift"

    async def _fetch_raw(self) -> list[dict]:
        results = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Try the Drift prediction markets endpoint
            for endpoint in [
                f"{DRIFT_GATEWAY}/markets",
                f"{DRIFT_GATEWAY}/v2/markets",
                "https://api.drift.trade/v1/markets",
            ]:
                try:
                    resp = await client.get(
                        endpoint,
                        params={"type": "prediction", "status": "active"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        markets = data if isinstance(data, list) else data.get("markets", data.get("data", data.get("result", [])))
                        if isinstance(markets, list) and len(markets) > 0:
                            for mkt in markets[:_MAX_MARKETS]:
                                result = self._parse_market(mkt)
                                if result:
                                    results.extend(result)
                            break
                except Exception as e:
                    logger.debug(f"Drift endpoint {endpoint} failed: {e}")
                    continue

        logger.info(f"Drift: fetched {len(results)} prices")
        return results

    def _parse_market(self, mkt: dict) -> list[dict]:
        results = []
        market_id = str(mkt.get("marketIndex", "") or mkt.get("id", "") or mkt.get("pubkey", ""))
        title = mkt.get("name", "") or mkt.get("title", "") or mkt.get("question", "")
        if not market_id or not title:
            return []

        volume = float(mkt.get("volume24h", 0) or mkt.get("volume", 0) or 0)
        category = categorise(title)

        # Parse price/probability
        prob = None
        for field in ["probability", "lastPrice", "markPrice", "oraclePrice", "price"]:
            val = mkt.get(field)
            if val is not None:
                try:
                    p = float(val)
                    # Drift sometimes stores prices in different units
                    if p > 100:
                        p = p / 1e6  # USDC precision
                    elif p > 1:
                        p = p / 100.0
                    if 0.01 < p < 0.99:
                        prob = p
                        break
                except (ValueError, TypeError):
                    continue

        if prob:
            results.append({
                "source": "drift",
                "market_id": market_id,
                "title": title,
                "outcome": "yes",
                "yes_price": round(prob, 4),
                "no_price": round(1 - prob, 4),
                "volume": volume,
                "category": category,
                "timestamp": datetime.now(timezone.utc),
                "metadata": {"url": f"https://app.drift.trade/bet/{market_id}"},
            })

        return results
