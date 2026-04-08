"""
Odds-API.io ingestion client.

Fetches sports odds from 265+ bookmakers via odds-api.io.
Free tier: 100 requests/hour, no credit card required.
This supplements The Odds API (the-odds-api.com) with far more bookmakers.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import httpx
import logging
from datetime import datetime, timezone, timedelta

import constants
from ingestion.base import BaseClient
from ingestion.categorize import categorise

logger = logging.getLogger(__name__)

ODDS_API_IO_BASE = "https://api.odds-api.io/v3"
ODDS_API_IO_KEY = os.getenv("ODDS_API_IO_KEY", "")

# Map their sport keys to our categories
SPORT_CATEGORY_MAP = {
    "soccer": "sports", "basketball": "sports", "football": "sports",
    "baseball": "sports", "hockey": "sports", "tennis": "sports",
    "mma": "sports", "boxing": "sports", "golf": "sports",
    "cricket": "sports", "rugby": "sports", "esports": "sports",
}


class OddsApiIoClient(BaseClient):
    """
    Fetches odds from Odds-API.io (265+ bookmakers).
    Falls back gracefully if no API key is configured.
    """

    source_name = "odds_api_io"

    def __init__(self):
        self.base_url = ODDS_API_IO_BASE
        self.api_key = ODDS_API_IO_KEY

    def _vig_strip(self, implied_probs: list[float]) -> list[float]:
        """Remove bookmaker vig using multiplicative method."""
        total = sum(implied_probs)
        if total == 0:
            return implied_probs
        return [p / total for p in implied_probs]

    async def _fetch_raw(self) -> list[dict]:
        if not self.api_key:
            logger.info("Odds-API.io: no API key configured — skipping")
            return []

        results: list[dict] = []

        async with httpx.AsyncClient(timeout=30) as client:
            # 1. Get available sports (apiKey as query param per docs)
            try:
                resp = await client.get(
                    f"{self.base_url}/sports",
                    params={"apiKey": self.api_key},
                )
                resp.raise_for_status()
                sports = resp.json()
                if isinstance(sports, dict):
                    sports = sports.get("data", [])
            except Exception as exc:
                logger.error(f"Odds-API.io sports list failed: {exc}")
                raise

            # 2. Fetch odds for first 5 sports (budget-friendly)
            sport_keys = [s.get("key") or s.get("id", "") for s in sports[:5]]
            cutoff = datetime.now(timezone.utc) + timedelta(days=7)

            for sport_key in sport_keys:
                try:
                    resp = await client.get(
                        f"{self.base_url}/events",
                        params={
                            "apiKey": self.api_key,
                            "sport": sport_key,
                            "regions": "us,eu,uk",
                            "markets": "h2h",
                            "oddsFormat": "decimal",
                        },
                    )
                    if resp.status_code != 200:
                        continue
                    events = resp.json()
                    if isinstance(events, dict):
                        events = events.get("data", [])

                    for event in events:
                        commence_str = event.get("commence_time", "")
                        try:
                            commence = datetime.fromisoformat(
                                commence_str.replace("Z", "+00:00")
                            )
                        except (ValueError, AttributeError):
                            continue
                        if commence > cutoff:
                            continue

                        away = event.get("away_team", "")
                        home = event.get("home_team", "")
                        event_name = f"{away} vs {home}"

                        for bookmaker in event.get("bookmakers", []):
                            bk_key = bookmaker.get("key", "odds_api_io")

                            for market in bookmaker.get("markets", []):
                                outcomes = market.get("outcomes", [])
                                raw_probs = []
                                for outcome in outcomes:
                                    decimal_odds = outcome.get("price", 0)
                                    raw_probs.append(
                                        1.0 / decimal_odds if decimal_odds > 0 else 0
                                    )
                                stripped = self._vig_strip(raw_probs)

                                for idx, outcome in enumerate(outcomes):
                                    decimal_odds = outcome.get("price", 0)
                                    prob = stripped[idx] if idx < len(stripped) else 0.0
                                    results.append({
                                        "source": f"io_{bk_key}",
                                        "market_id": f"{event.get('id', '')}_{market.get('key', 'h2h')}",
                                        "title": event_name,
                                        "outcome": outcome.get("name", ""),
                                        "yes_price": prob,
                                        "no_price": 1.0 - prob,
                                        "raw_odds": decimal_odds,
                                        "category": "sports",
                                        "timestamp": datetime.now(timezone.utc),
                                        "metadata": {"sport": sport_key},
                                    })

                except Exception as exc:
                    logger.debug(f"Odds-API.io: failed to fetch {sport_key}: {exc}")
                    continue

        return results
