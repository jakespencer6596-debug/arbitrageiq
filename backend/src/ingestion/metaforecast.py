"""
Metaforecast aggregator ingestion client.

Fetches prediction data from 10+ platforms via a single GraphQL API call.
Platforms include: Metaculus, Polymarket, Kalshi, Manifold, GJOpen, INFER,
Hypermind, Rootclaim, and more.

Used for cross-platform price comparison and value bet detection.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
import httpx
import logging
from datetime import datetime, timezone

import constants
from db.models import SessionLocal, MarketPrice, SystemStatus
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)

METAFORECAST_URL = "https://metaforecast.org/api/graphql"

GRAPHQL_QUERY = """
{
  questions(first: 200) {
    edges {
      node {
        id
        title
        url
        platform {
          id
          label
        }
        options {
          name
          probability
        }
        qualityIndicators {
          numForecasts
          volume
        }
      }
    }
  }
}
"""

# Map Metaforecast platform IDs to our source names
PLATFORM_MAP = {
    "metaculus": "metaculus",
    "polymarket": "polymarket_mf",  # suffix to avoid collision with direct Polymarket ingestion
    "kalshi": "kalshi_mf",
    "manifold": "manifold_mf",
    "goodjudgmentopen": "gjopen",
    "infer": "infer",
    "hypermind": "hypermind",
    "rootclaim": "rootclaim",
    "predictit": None,  # Skip — we dropped PredictIt
}


class MetaforecastClient:
    """
    Fetches cross-platform prediction data from the Metaforecast aggregator.
    One GraphQL call returns data from 10+ prediction platforms.
    """

    def _update_system_status(self, error: str | None = None) -> None:
        try:
            db = SessionLocal()
            try:
                status = db.query(SystemStatus).filter(SystemStatus.source == "metaforecast").first()
                if not status:
                    status = SystemStatus(source="metaforecast", component="metaforecast")
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
            logger.debug(f"Could not update SystemStatus for metaforecast: {exc}")

    async def fetch(self) -> list[dict]:
        """
        Fetch prediction data from Metaforecast GraphQL API.
        Returns normalized rows for value bet comparison.
        """
        if constants.ACTIVE_CATEGORY is None:
            logger.info("Metaforecast: no active category — skipping")
            return []

        results: list[dict] = []

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    METAFORECAST_URL,
                    json={"query": GRAPHQL_QUERY},
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()

            questions = data.get("data", {}).get("questions", {}).get("edges", [])
            logger.info(f"Metaforecast: received {len(questions)} questions")

            for edge in questions:
                node = edge.get("node", {})
                title = node.get("title", "")
                url = node.get("url", "")
                platform = node.get("platform", {})
                platform_id = platform.get("id", "").lower()
                platform_label = platform.get("label", "")
                options = node.get("options", [])
                quality = node.get("qualityIndicators", {})
                num_forecasts = quality.get("numForecasts", 0) or 0
                volume = quality.get("volume", 0) or 0

                # Map to our source name
                source = PLATFORM_MAP.get(platform_id, platform_id)
                if source is None:
                    continue  # Skip dropped platforms

                category = categorise(title)

                # Only keep markets matching active category
                if category != constants.ACTIVE_CATEGORY:
                    continue

                # Extract YES probability from options
                yes_prob = None
                for opt in options:
                    name = (opt.get("name", "") or "").lower()
                    prob = opt.get("probability")
                    if prob is not None and name in ("yes", ""):
                        yes_prob = prob
                        break
                if yes_prob is None and options:
                    yes_prob = options[0].get("probability")

                if yes_prob is None or yes_prob <= 0 or yes_prob >= 1:
                    continue

                results.append({
                    "source": source,
                    "platform_label": platform_label,
                    "market_id": node.get("id", ""),
                    "title": title,
                    "url": url,
                    "yes_price": yes_prob,
                    "category": category,
                    "volume": volume,
                    "num_forecasts": num_forecasts,
                    "timestamp": datetime.now(timezone.utc),
                })

        except Exception as exc:
            logger.error(f"Metaforecast fetch failed: {exc}")
            self._update_system_status(error=str(exc))
            return results

        logger.info(f"Metaforecast: {len(results)} rows match active category '{constants.ACTIVE_CATEGORY}'")

        if not results:
            self._update_system_status()
            return results

        # Persist to database
        try:
            db = SessionLocal()
            try:
                # Deactivate old metaforecast prices
                for src in set(r["source"] for r in results):
                    db.query(MarketPrice).filter(
                        MarketPrice.source == src,
                        MarketPrice.is_active == True,
                    ).update({"is_active": False})

                for r in results:
                    db.add(MarketPrice(
                        source=r["source"],
                        market_id=r["market_id"],
                        event_name=r["title"],
                        market_title=r["title"],
                        outcome="yes",
                        implied_probability=r["yes_price"],
                        category=r["category"],
                        yes_price=r["yes_price"],
                        no_price=round(1.0 - r["yes_price"], 4),
                        volume=r["volume"],
                        raw_payload=None,
                        fetched_at=r["timestamp"],
                        metadata_={"url": r["url"], "platform": r["platform_label"], "num_forecasts": r["num_forecasts"]},
                    ))

                db.commit()
                logger.info(f"Saved {len(results)} Metaforecast prices to database")
            finally:
                db.close()
        except Exception as exc:
            logger.error(f"Failed to save Metaforecast data to DB: {exc}")
            self._update_system_status(error=str(exc))
            return results

        self._update_system_status()
        return results
