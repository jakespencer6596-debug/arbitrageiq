"""
Limitless Exchange prediction market ingestion client.

Limitless (limitless.exchange) is a leading prediction market on Base chain.
Real money (crypto), free REST API, covers crypto/macro/politics.
"""

import httpx
import logging
from datetime import datetime, timezone

from ingestion.base import BaseClient
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)

LIMITLESS_API_BASE = "https://api.limitless.exchange/api-v1"
_MAX_MARKETS = 200


class LimitlessClient(BaseClient):
    source_name = "limitless"

    async def _fetch_raw(self) -> list[dict]:
        results = []

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{LIMITLESS_API_BASE}/markets",
                params={"status": "active", "limit": _MAX_MARKETS},
            )
            resp.raise_for_status()
            data = resp.json()

            markets = data if isinstance(data, list) else data.get("markets", data.get("results", data.get("data", [])))
            if not isinstance(markets, list):
                markets = []

            for mkt in markets:
                market_id = str(mkt.get("id", "") or mkt.get("address", "") or mkt.get("slug", ""))
                title = mkt.get("title", "") or mkt.get("question", "") or mkt.get("name", "")
                if not market_id or not title:
                    continue

                volume = float(mkt.get("volume", 0) or mkt.get("totalVolume", 0) or 0)
                category = categorise(title)
                slug = mkt.get("slug", market_id)
                url = f"https://limitless.exchange/markets/{slug}"
                end_date = mkt.get("expirationDate", "") or mkt.get("deadline", "") or mkt.get("endDate", "")

                # Parse probability from various possible fields
                prob = None
                for field in ["probability", "lastPrice", "yes_price", "currentPrice", "price"]:
                    val = mkt.get(field)
                    if val is not None:
                        try:
                            p = float(val)
                            if p > 1:
                                p = p / 100.0
                            if 0.01 < p < 0.99:
                                prob = p
                                break
                        except (ValueError, TypeError):
                            continue

                if prob:
                    results.append({
                        "source": "limitless",
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

                # Multi-outcome markets
                outcomes = mkt.get("outcomes", []) or mkt.get("options", [])
                for out in outcomes:
                    label = out.get("title", "") or out.get("name", "") or out.get("label", "")
                    price = out.get("price") or out.get("probability") or out.get("lastPrice")
                    if price is None or not label:
                        continue
                    try:
                        price = float(price)
                        if price > 1:
                            price = price / 100.0
                    except (ValueError, TypeError):
                        continue

                    if 0.01 < price < 0.99:
                        out_id = out.get("id", label[:10].lower().replace(" ", "_"))
                        results.append({
                            "source": "limitless",
                            "market_id": f"{market_id}_{out_id}",
                            "title": f"{title}: {label}" if label.lower() not in ("yes", "no") else title,
                            "outcome": label.lower() if label.lower() in ("yes", "no") else label,
                            "yes_price": price,
                            "volume": volume,
                            "category": category,
                            "timestamp": datetime.now(timezone.utc),
                            "metadata": {"url": url, "end_date": end_date},
                        })

        logger.info(f"Limitless: fetched {len(results)} prices")
        return results
