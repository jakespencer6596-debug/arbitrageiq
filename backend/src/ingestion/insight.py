"""
Insight Prediction market ingestion client.

Insight Prediction (insightprediction.com) is a CFTC-regulated
real-money prediction market. Public API, no auth required.
Covers US politics, economics, geopolitics, and tech.
"""

import httpx
import logging
from datetime import datetime, timezone

from ingestion.base import BaseClient
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)

INSIGHT_API_BASE = "https://insightprediction.com/api/v1"
_MAX_MARKETS = 200


class InsightClient(BaseClient):
    source_name = "insight"

    async def _fetch_raw(self) -> list[dict]:
        results = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Try markets endpoint
            resp = await client.get(
                f"{INSIGHT_API_BASE}/markets",
                params={"status": "open", "limit": _MAX_MARKETS},
            )
            resp.raise_for_status()
            data = resp.json()

            markets = data.get("markets", data.get("results", data))
            if isinstance(markets, dict) and "data" in markets:
                markets = markets["data"]
            if not isinstance(markets, list):
                markets = []

            for mkt in markets:
                market_id = str(mkt.get("id", ""))
                title = mkt.get("title", "") or mkt.get("question", "") or mkt.get("name", "")
                if not market_id or not title:
                    continue

                volume = mkt.get("volume", 0) or mkt.get("total_volume", 0) or 0
                category = categorise(title)
                slug = mkt.get("slug", "")
                url = f"https://insightprediction.com/m/{slug}" if slug else f"https://insightprediction.com/m/{market_id}"
                end_date = mkt.get("end_date", "") or mkt.get("close_date", "") or mkt.get("resolution_date", "")

                # Parse probability
                prob = mkt.get("probability") or mkt.get("yes_price") or mkt.get("last_price") or mkt.get("current_price")
                if prob is not None:
                    try:
                        prob = float(prob)
                        # Some APIs return percentage (0-100) vs decimal (0-1)
                        if prob > 1:
                            prob = prob / 100.0
                    except (ValueError, TypeError):
                        prob = None

                if prob and 0.01 < prob < 0.99:
                    results.append({
                        "source": "insight",
                        "market_id": market_id,
                        "title": title,
                        "outcome": "yes",
                        "yes_price": prob,
                        "no_price": 1 - prob,
                        "volume": volume,
                        "category": category,
                        "timestamp": datetime.now(timezone.utc),
                        "metadata": {"url": url, "end_date": end_date},
                    })

                # Also parse outcomes/contracts if available
                outcomes = mkt.get("outcomes", []) or mkt.get("contracts", [])
                for out in outcomes:
                    out_id = out.get("id", "")
                    label = out.get("title", "") or out.get("name", "")
                    price = out.get("price") or out.get("probability") or out.get("last_price")
                    if price is None or not label:
                        continue
                    try:
                        price = float(price)
                        if price > 1:
                            price = price / 100.0
                    except (ValueError, TypeError):
                        continue

                    if 0.01 < price < 0.99:
                        results.append({
                            "source": "insight",
                            "market_id": f"{market_id}_{out_id}" if out_id else market_id,
                            "title": f"{title}: {label}" if label.lower() not in ("yes", "no") else title,
                            "outcome": label.lower() if label.lower() in ("yes", "no") else label,
                            "yes_price": price,
                            "volume": volume,
                            "category": category,
                            "timestamp": datetime.now(timezone.utc),
                            "metadata": {"url": url, "end_date": end_date},
                        })

        logger.info(f"Insight: fetched {len(results)} prices")
        return results
