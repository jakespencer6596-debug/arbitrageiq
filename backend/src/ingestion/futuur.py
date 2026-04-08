"""
Futuur prediction market ingestion client.

Futuur (futuur.com) is a real-money prediction market covering politics,
economics, sports, crypto, and culture. Public API, no auth required.
"""

import httpx
import logging
from datetime import datetime, timezone

from ingestion.base import BaseClient
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)

FUTUUR_API_BASE = "https://api.futuur.com/api/v1"
_PAGE_SIZE = 50
_MAX_PAGES = 5


class FutuurClient(BaseClient):
    source_name = "futuur"

    async def _fetch_raw(self) -> list[dict]:
        results = []
        page = 1

        async with httpx.AsyncClient(timeout=30) as client:
            while page <= _MAX_PAGES:
                resp = await client.get(
                    f"{FUTUUR_API_BASE}/markets/",
                    params={
                        "status": "open",
                        "page": page,
                        "page_size": _PAGE_SIZE,
                        "ordering": "-volume",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

                markets = data.get("results", data) if isinstance(data, dict) else data
                if not markets or not isinstance(markets, list):
                    break

                for mkt in markets:
                    market_id = str(mkt.get("id", ""))
                    title = mkt.get("title", "") or mkt.get("question", "")
                    if not market_id or not title:
                        continue

                    volume = mkt.get("volume", 0) or 0
                    category = categorise(title)
                    url = mkt.get("url", f"https://futuur.com/q/{market_id}")
                    end_date = mkt.get("end_date", "") or mkt.get("resolve_date", "")

                    # Parse outcomes/choices
                    outcomes = mkt.get("outcomes", []) or mkt.get("choices", [])
                    if not outcomes:
                        # Try yes/no from probability field
                        prob = mkt.get("probability") or mkt.get("yes_price")
                        if prob and 0 < float(prob) < 1:
                            p = float(prob)
                            results.append({
                                "source": "futuur",
                                "market_id": market_id,
                                "title": title,
                                "outcome": "yes",
                                "yes_price": p,
                                "no_price": 1 - p,
                                "volume": volume,
                                "category": category,
                                "timestamp": datetime.now(timezone.utc),
                                "metadata": {"url": url, "end_date": end_date},
                            })
                        continue

                    yes_price = None
                    no_price = None

                    for out in outcomes:
                        label = out.get("title", "") or out.get("name", "") or out.get("label", "")
                        price = out.get("price") or out.get("probability") or out.get("last_price")
                        if price is None:
                            continue
                        try:
                            price = float(price)
                        except (ValueError, TypeError):
                            continue

                        if price <= 0 or price >= 1:
                            continue

                        label_lower = label.lower()
                        if label_lower in ("yes", "true") or (len(outcomes) == 2 and outcomes.index(out) == 0):
                            yes_price = price
                        if label_lower in ("no", "false") or (len(outcomes) == 2 and outcomes.index(out) == 1):
                            no_price = price

                        results.append({
                            "source": "futuur",
                            "market_id": f"{market_id}_{out.get('id', label_lower[:10])}",
                            "title": f"{title}: {label}" if len(outcomes) > 2 else title,
                            "outcome": label_lower if label_lower in ("yes", "no") else label,
                            "yes_price": price,
                            "no_price": 1 - price if len(outcomes) == 2 else None,
                            "volume": volume,
                            "category": category,
                            "timestamp": datetime.now(timezone.utc),
                            "metadata": {"url": url, "end_date": end_date},
                        })

                page += 1
                if isinstance(data, dict) and not data.get("next"):
                    break
                if len(markets) < _PAGE_SIZE:
                    break

        logger.info(f"Futuur: fetched {len(results)} prices from {page - 1} pages")
        return results
