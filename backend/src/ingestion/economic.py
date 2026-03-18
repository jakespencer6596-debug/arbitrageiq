"""
Economic-data ingestion client for ArbitrageIQ.

Fetches macroeconomic indicators from the FRED API and cryptocurrency
prices from CoinGecko.  For each FRED series the module:

  1. Pulls the latest 5 observations.
  2. Detects new data releases by comparing against the last stored date.
  3. Converts the latest value into a normalised probability using recent
     standard deviation.

CoinGecko prices are fetched for BTC and ETH (free tier, no key needed).
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import math
import httpx
import logging
from datetime import datetime, timezone
from typing import Any

from constants import FRED_API_KEY, FRED_BASE, FRED_SERIES
from db.models import SessionLocal, MarketPrice, TrackedMarket, SystemStatus

logger = logging.getLogger(__name__)

_COINGECKO_BASE = "https://api.coingecko.com/api/v3"
_COINGECKO_COINS = ["bitcoin", "ethereum"]


def _clamp(value: float, low: float, high: float) -> float:
    """
    Clamp a numeric value to a closed interval.

    Args:
        value: The value to clamp.
        low: Lower bound.
        high: Upper bound.

    Returns:
        The clamped value.
    """
    return max(low, min(high, value))


def _compute_std(values: list[float]) -> float:
    """
    Compute the sample standard deviation of a list of floats.

    If fewer than 2 values are available, returns 1.0 as a safe default
    to avoid division by zero in the probability formula.

    Args:
        values: A list of numeric observations.

    Returns:
        The sample standard deviation (or 1.0 if not enough data).
    """
    if len(values) < 2:
        return 1.0
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return math.sqrt(variance) if variance > 0 else 1.0


def _value_to_probability(
    current: float,
    target: float,
    recent_std: float,
) -> float:
    """
    Convert a FRED indicator value to a normalised probability.

    Uses the formula:
        prob = clamp(0.5 + (current - target) / (2 * recent_std), 0.05, 0.95)

    This yields 0.5 when current equals target and shifts linearly toward
    0.05 or 0.95 as the value moves away from the target.  The ``target``
    is the mean of recent observations, so the probability reflects how
    extreme the latest reading is relative to recent history.

    Args:
        current: The latest FRED observation value.
        target: The reference value (typically the mean of recent obs).
        recent_std: The standard deviation of recent observations.

    Returns:
        A probability between 0.05 and 0.95.
    """
    if recent_std <= 0:
        recent_std = 1.0
    raw = 0.5 + (current - target) / (2.0 * recent_std)
    return _clamp(raw, 0.05, 0.95)


class EconomicClient:
    """
    Async client for FRED macroeconomic data and CoinGecko crypto prices.

    For each FRED_SERIES defined in constants the client:
      - Fetches the latest 5 observations.
      - Detects new releases (dates not yet seen).
      - Converts the value to an implied probability.
      - Writes MarketPrice rows and auto-tracks new markets.

    Additionally fetches BTC/ETH prices from CoinGecko (free, no API key).
    """

    def __init__(self) -> None:
        """Initialise with the FRED base URL and API key from constants."""
        self.fred_base = FRED_BASE
        self.fred_key = FRED_API_KEY

    def _update_system_status(
        self,
        component: str,
        error: str | None = None,
    ) -> None:
        """
        Persist ingestor health information to the SystemStatus table.

        Args:
            component: The component name (e.g. 'fred', 'coingecko').
            error: If not None, the error message to record.
        """
        try:
            db = SessionLocal()
            try:
                status = (
                    db.query(SystemStatus)
                    .filter(SystemStatus.source == component)
                    .first()
                )
                if not status:
                    status = SystemStatus(source=component, component=component)
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

                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.debug(
                f"Could not update SystemStatus for {component}: {exc}"
            )

    def _upsert_tracked_market(
        self,
        db,
        source: str,
        market_id: str,
        title: str,
        category: str,
    ) -> None:
        """
        Insert or update a TrackedMarket row for auto-discovery.

        Args:
            db: An active SQLAlchemy session.
            source: The data source identifier.
            market_id: The market identifier (e.g. FRED series ID).
            title: Human-readable label.
            category: The classified category.
        """
        existing = (
            db.query(TrackedMarket)
            .filter(
                TrackedMarket.source == source,
                TrackedMarket.market_id == market_id,
            )
            .first()
        )
        if not existing:
            db.add(
                TrackedMarket(
                    source=source,
                    market_id=market_id,
                    event_name=title,
                    market_title=title,
                    category=category,
                    is_active=True,
                )
            )

    def _get_last_stored_date(self, db, series_id: str) -> str | None:
        """
        Look up the most recent observation date already stored for a FRED series.

        Used to detect new data releases: if the API returns a date later
        than this, a new observation has been published.

        Args:
            db: An active SQLAlchemy session.
            series_id: The FRED series identifier.

        Returns:
            An ISO date string (e.g. '2024-01-01') or None if no prior
            data exists.
        """
        latest = (
            db.query(MarketPrice)
            .filter(
                MarketPrice.source == "fred",
                MarketPrice.market_id == series_id,
            )
            .order_by(MarketPrice.fetched_at.desc())
            .first()
        )
        if latest and latest.raw_payload:
            return latest.raw_payload.get("observation_date")
        return None

    async def _fetch_fred_series(
        self,
        client: httpx.AsyncClient,
        series_id: str,
    ) -> list[dict]:
        """
        Fetch the latest 5 observations for a single FRED series.

        Args:
            client: An active httpx.AsyncClient.
            series_id: The FRED series identifier (e.g. 'CPIAUCSL').

        Returns:
            A list of observation dicts with 'date' and 'value' keys,
            sorted newest-first.  Returns an empty list on failure.
        """
        if not self.fred_key:
            logger.warning("No FRED_API_KEY configured -- skipping FRED")
            return []

        try:
            resp = await client.get(
                f"{self.fred_base}/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": self.fred_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": 5,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("observations", [])
        except Exception as exc:
            logger.error(f"FRED fetch failed for {series_id}: {exc}")
            return []

    async def _fetch_coingecko(
        self,
        client: httpx.AsyncClient,
    ) -> list[dict]:
        """
        Fetch current prices for BTC and ETH from CoinGecko.

        Uses the ``/simple/price`` endpoint which is free and requires no
        API key.

        Args:
            client: An active httpx.AsyncClient.

        Returns:
            A list of dicts with keys: coin, price_usd, market_cap,
            volume_24h, change_24h.  Returns an empty list on failure.
        """
        try:
            ids = ",".join(_COINGECKO_COINS)
            resp = await client.get(
                f"{_COINGECKO_BASE}/simple/price",
                params={
                    "ids": ids,
                    "vs_currencies": "usd",
                    "include_market_cap": "true",
                    "include_24hr_vol": "true",
                    "include_24hr_change": "true",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            results = []
            for coin in _COINGECKO_COINS:
                info = data.get(coin, {})
                if not info:
                    continue
                results.append(
                    {
                        "coin": coin,
                        "price_usd": info.get("usd", 0),
                        "market_cap": info.get("usd_market_cap", 0),
                        "volume_24h": info.get("usd_24h_vol", 0),
                        "change_24h": info.get("usd_24h_change", 0),
                    }
                )
            return results

        except Exception as exc:
            logger.error(f"CoinGecko fetch failed: {exc}")
            return []

    async def fetch(self) -> dict[str, Any]:
        """
        Main fetch method for all economic data sources.

        Performs two tasks in sequence:

        1. **FRED series**: For each series in ``FRED_SERIES``, fetches
           the latest 5 observations, detects new releases, computes a
           normalised probability, and writes to MarketPrice + TrackedMarket.

        2. **CoinGecko crypto prices**: Fetches BTC/ETH spot prices and
           writes to MarketPrice.

        Updates SystemStatus for both 'fred' and 'coingecko' components.

        Returns:
            A dict with keys:
              - 'fred': list of per-series result dicts
              - 'crypto': list of per-coin result dicts
              - 'new_releases': list of series IDs that had new data
              - 'timestamp': ISO-formatted fetch time
        """
        fred_results: list[dict] = []
        crypto_results: list[dict] = []
        new_releases: list[str] = []
        now = datetime.now(timezone.utc)

        async with httpx.AsyncClient(timeout=30) as client:
            # ==============================================================
            # FRED series
            # ==============================================================
            db = None
            try:
                db = SessionLocal()

                for series_id, meta in FRED_SERIES.items():
                    observations = await self._fetch_fred_series(
                        client, series_id
                    )
                    if not observations:
                        continue

                    # Parse numeric values (FRED uses '.' for missing)
                    numeric_values: list[float] = []
                    for obs in observations:
                        raw_val = obs.get("value", ".")
                        if raw_val == "." or raw_val is None:
                            continue
                        try:
                            numeric_values.append(float(raw_val))
                        except (ValueError, TypeError):
                            continue

                    if not numeric_values:
                        continue

                    current_value = numeric_values[0]
                    recent_std = _compute_std(numeric_values)
                    target = (
                        sum(numeric_values) / len(numeric_values)
                    )
                    probability = _value_to_probability(
                        current_value, target, recent_std
                    )

                    # Detect new releases
                    latest_date = observations[0].get("date", "")
                    last_stored = self._get_last_stored_date(db, series_id)
                    is_new_release = (
                        last_stored is None or latest_date > last_stored
                    )
                    if is_new_release:
                        new_releases.append(series_id)
                        logger.info(
                            f"New FRED release detected: {series_id} "
                            f"date={latest_date}"
                        )

                    result = {
                        "series_id": series_id,
                        "label": meta["label"],
                        "unit": meta["unit"],
                        "latest_value": current_value,
                        "latest_date": latest_date,
                        "recent_mean": round(target, 4),
                        "recent_std": round(recent_std, 4),
                        "implied_probability": round(probability, 4),
                        "is_new_release": is_new_release,
                        "observations": [
                            {
                                "date": obs.get("date"),
                                "value": obs.get("value"),
                            }
                            for obs in observations
                        ],
                    }
                    fred_results.append(result)

                    # Write to MarketPrice
                    db.add(
                        MarketPrice(
                            source="fred",
                            market_id=series_id,
                            event_name=meta["label"],
                            market_title=meta["label"],
                            outcome="yes",
                            implied_probability=probability,
                            category="economic",
                            yes_price=probability,
                            no_price=1.0 - probability,
                            last_traded_price=current_value,
                            raw_payload={
                                "observation_date": latest_date,
                                "value": current_value,
                                "unit": meta["unit"],
                                "recent_std": round(recent_std, 4),
                                "recent_mean": round(target, 4),
                            },
                            fetched_at=now,
                        )
                    )

                    # Auto-track
                    self._upsert_tracked_market(
                        db, "fred", series_id, meta["label"], "economic"
                    )

                db.commit()
                logger.info(
                    f"Saved {len(fred_results)} FRED series to database"
                )

            except Exception as exc:
                logger.error(f"FRED processing failed: {exc}")
                self._update_system_status("fred", error=str(exc))
                if db:
                    try:
                        db.rollback()
                    except Exception:
                        pass
            finally:
                if db:
                    db.close()

            if fred_results:
                self._update_system_status("fred")

            # ==============================================================
            # CoinGecko crypto prices
            # ==============================================================
            try:
                raw_crypto = await self._fetch_coingecko(client)

                if raw_crypto:
                    db = SessionLocal()
                    try:
                        for coin_data in raw_crypto:
                            coin = coin_data["coin"]
                            price = coin_data["price_usd"]
                            change = coin_data.get("change_24h", 0)

                            # Simple directional probability:
                            # >0% change => bullish probability, <0 => bearish
                            # Normalise: clamp(0.5 + change/200, 0.05, 0.95)
                            prob = _clamp(
                                0.5 + (change / 200.0), 0.05, 0.95
                            )

                            crypto_results.append(
                                {
                                    "coin": coin,
                                    "price_usd": price,
                                    "change_24h_pct": round(change, 2),
                                    "implied_probability": round(prob, 4),
                                    "market_cap": coin_data.get(
                                        "market_cap", 0
                                    ),
                                    "volume_24h": coin_data.get(
                                        "volume_24h", 0
                                    ),
                                }
                            )

                            db.add(
                                MarketPrice(
                                    source="coingecko",
                                    market_id=f"crypto_{coin}",
                                    event_name=f"{coin.title()} USD Price",
                                    market_title=f"{coin.title()} USD Price",
                                    outcome="yes",
                                    implied_probability=prob,
                                    category="economic",
                                    yes_price=prob,
                                    no_price=1.0 - prob,
                                    last_traded_price=price,
                                    volume=coin_data.get("volume_24h"),
                                    raw_payload=coin_data,
                                    fetched_at=now,
                                )
                            )

                            self._upsert_tracked_market(
                                db,
                                "coingecko",
                                f"crypto_{coin}",
                                f"{coin.title()} USD Price",
                                "economic",
                            )

                        db.commit()
                        logger.info(
                            f"Saved {len(crypto_results)} crypto prices "
                            "to database"
                        )
                    finally:
                        db.close()

                    self._update_system_status("coingecko")

            except Exception as exc:
                logger.error(f"CoinGecko processing failed: {exc}")
                self._update_system_status("coingecko", error=str(exc))

        return {
            "fred": fred_results,
            "crypto": crypto_results,
            "new_releases": new_releases,
            "timestamp": now.isoformat(),
        }
