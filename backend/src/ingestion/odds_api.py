"""
The Odds API ingestion client.
Fetches sports odds from multiple bookmakers.
Budget-aware: rotates through sport groups to stay within 500 req/month free tier.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import httpx
import logging
from datetime import datetime, timedelta, timezone

from constants import ODDS_API_KEY, ODDS_API_BASE, BUDGET_MODE
from db.models import SessionLocal, MarketPrice, SystemStatus

logger = logging.getLogger(__name__)

# Track which sport batch we're on for rotation
_current_batch_index = 0
_BATCH_SIZE = 3  # Reduced to conserve free-tier credits (500/month)


def _classify_sport(sport_key: str) -> str:
    """Map an Odds API sport key to an ArbitrageIQ category."""
    return "sports"


class OddsAPIClient:
    """
    Fetches odds from The Odds API.

    In BUDGET_MODE, rotates through sports in batches of 5 to conserve credits.
    Tracks x-requests-remaining header and persists credit information to
    the SystemStatus table.
    """

    def __init__(self) -> None:
        """Initialise the client with base URL and API key from constants."""
        self.base_url = ODDS_API_BASE
        self.api_key = ODDS_API_KEY

    async def _get_sports(self, client: httpx.AsyncClient) -> list[dict]:
        """
        Fetch all available sports from The Odds API.

        This endpoint costs 0 API credits.

        Returns:
            A list of sport dicts, each containing at minimum a 'key' field
            and optionally 'has_outrights'.
        """
        resp = await client.get(
            f"{self.base_url}/sports",
            params={"apiKey": self.api_key},
        )
        resp.raise_for_status()
        return resp.json()

    def _vig_strip(self, implied_probs: list[float]) -> list[float]:
        """
        Remove the bookmaker's vig (overround) using the multiplicative method.

        Each raw implied probability is divided by the sum of all implied
        probabilities so the resulting set sums to 1.0.

        Args:
            implied_probs: Raw implied probabilities (may sum to > 1.0).

        Returns:
            Vig-free probabilities that sum to 1.0.
        """
        total = sum(implied_probs)
        if total == 0:
            return implied_probs
        return [p / total for p in implied_probs]

    def _update_system_status(
        self,
        remaining: str,
        used: str,
        error: str | None = None,
    ) -> None:
        """
        Persist Odds API health and credit info to the SystemStatus table.

        Args:
            remaining: Value of the x-requests-remaining response header.
            used: Value of the x-requests-used response header.
            error: If not None, an error message to record.
        """
        try:
            db = SessionLocal()
            try:
                status = (
                    db.query(SystemStatus)
                    .filter(SystemStatus.source == "odds_api")
                    .first()
                )
                if not status:
                    status = SystemStatus(source="odds_api", component="odds_api")
                    db.add(status)

                now = datetime.now(timezone.utc)

                if error:
                    status.status = "degraded"
                    status.last_failure_at = now
                    status.last_error = error
                    status.consecutive_failures = (
                        (status.consecutive_failures or 0) + 1
                    )
                else:
                    status.status = "healthy"
                    status.last_success_at = now
                    status.consecutive_failures = 0

                status.metadata_ = {
                    "credits_remaining": remaining,
                    "credits_used": used,
                }
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.debug(f"Could not update SystemStatus for odds_api: {exc}")

    async def fetch(self) -> list[dict]:
        """
        Main fetch method.

        Returns a list of normalised market-price dicts, one per outcome per
        bookmaker per event.  In BUDGET_MODE the method only fetches one batch
        of sports per invocation and rotates through the full list across
        successive calls.

        Side-effects:
            - Writes MarketPrice rows to the database.
            - Updates SystemStatus with remaining API credits.

        Returns:
            List of dicts with keys: source, market_id, event_name, outcome,
            implied_probability, raw_odds, category, timestamp, metadata.
        """
        global _current_batch_index

        if not self.api_key:
            logger.warning("No ODDS_API_KEY configured -- skipping odds fetch")
            return []

        results: list[dict] = []
        remaining_header = "unknown"
        used_header = "unknown"

        async with httpx.AsyncClient(timeout=30) as client:
            # ------------------------------------------------------------------
            # 1. Discover available sports (free call -- 0 credits)
            # ------------------------------------------------------------------
            try:
                all_sports = await self._get_sports(client)
                active_sports = [
                    s for s in all_sports if not s.get("has_outrights", False)
                ]
                sport_keys = [s["key"] for s in active_sports]
            except Exception as exc:
                logger.error(f"Failed to fetch sports list: {exc}")
                self._update_system_status("unknown", "unknown", error=str(exc))
                return []

            # ------------------------------------------------------------------
            # 2. Apply budget-mode batch rotation
            # ------------------------------------------------------------------
            if BUDGET_MODE:
                start = _current_batch_index * _BATCH_SIZE
                batch = sport_keys[start : start + _BATCH_SIZE]
                if not batch:
                    _current_batch_index = 0
                    batch = sport_keys[:_BATCH_SIZE]
                else:
                    _current_batch_index += 1
                sport_keys = batch
                logger.info(
                    f"Budget mode: fetching batch {_current_batch_index} -- "
                    f"{sport_keys}"
                )

            # ------------------------------------------------------------------
            # 3. Fetch odds per sport
            # ------------------------------------------------------------------
            cutoff = datetime.now(timezone.utc) + timedelta(days=7)

            for sport_key in sport_keys:
                try:
                    resp = await client.get(
                        f"{self.base_url}/sports/{sport_key}/odds",
                        params={
                            "apiKey": self.api_key,
                            "regions": "us,us2",
                            "markets": "h2h,spreads",
                            "oddsFormat": "decimal",
                            "dateFormat": "iso",
                        },
                    )
                    resp.raise_for_status()

                    remaining_header = resp.headers.get(
                        "x-requests-remaining", "unknown"
                    )
                    used_header = resp.headers.get("x-requests-used", "unknown")
                    logger.info(
                        f"Odds API credits -- remaining: {remaining_header}, "
                        f"used: {used_header}"
                    )

                    events = resp.json()

                    for event in events:
                        # Only include events within the next 7 days
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
                            source = bookmaker["key"]

                            for market in bookmaker.get("markets", []):
                                market_type = market["key"]  # h2h, spreads
                                outcomes = market.get("outcomes", [])

                                # -- implied probabilities (vig-stripped) ------
                                raw_probs = []
                                for outcome in outcomes:
                                    decimal_odds = outcome.get("price", 0)
                                    raw_probs.append(
                                        1.0 / decimal_odds
                                        if decimal_odds > 0
                                        else 0
                                    )

                                stripped = self._vig_strip(raw_probs)

                                for idx, outcome in enumerate(outcomes):
                                    decimal_odds = outcome.get("price", 0)
                                    results.append(
                                        {
                                            "source": source,
                                            "market_id": (
                                                f"{event['id']}_{market_type}"
                                            ),
                                            "event_name": event_name,
                                            "outcome": outcome["name"],
                                            "implied_probability": (
                                                stripped[idx]
                                                if idx < len(stripped)
                                                else 0.0
                                            ),
                                            "raw_odds": decimal_odds,
                                            "category": _classify_sport(
                                                sport_key
                                            ),
                                            "timestamp": datetime.now(
                                                timezone.utc
                                            ),
                                            "metadata": {
                                                "sport": sport_key,
                                                "market_type": market_type,
                                                "commence_time": commence_str,
                                                "point": outcome.get("point"),
                                            },
                                        }
                                    )

                except Exception as exc:
                    logger.error(
                        f"Failed to fetch odds for {sport_key}: {exc}"
                    )
                    continue

        # ------------------------------------------------------------------
        # 4. Persist to database
        # ------------------------------------------------------------------
        try:
            db = SessionLocal()
            try:
                for r in results:
                    db.add(
                        MarketPrice(
                            source=r["source"],
                            market_id=r["market_id"],
                            event_name=r["event_name"],
                            market_title=r["event_name"],
                            outcome=r["outcome"],
                            implied_probability=r["implied_probability"],
                            category=r["category"],
                            yes_price=r["implied_probability"],
                            no_price=1.0 - r["implied_probability"],
                            raw_odds=r["raw_odds"],
                            last_traded_price=r["raw_odds"],
                            raw_payload=None,
                            fetched_at=r["timestamp"],
                        )
                    )
                db.commit()
                logger.info(f"Saved {len(results)} odds prices to database")
            finally:
                db.close()
        except Exception as exc:
            logger.error(f"Failed to save odds to DB: {exc}")

        # Update system health
        self._update_system_status(remaining_header, used_header)

        return results
