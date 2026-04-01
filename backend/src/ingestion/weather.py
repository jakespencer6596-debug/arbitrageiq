"""
Weather ingestion and probability-model client.

Enriches weather-related TrackedMarkets with:
  - Open-Meteo daily forecasts (temperature, precipitation, wind)
  - 30-day historical data for z-score probability modelling
  - NWS active weather alerts

For threshold-style markets (e.g. "Will temp exceed 100 F?") the module
computes a probability using ``1 - norm.cdf((threshold - forecast) / sigma)``
based on recent historical volatility.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import re
import math
import httpx
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from constants import (
    OPEN_METEO_URL,
    OPEN_METEO_HISTORICAL_URL,
    NWS_API_URL,
)
from db.models import SessionLocal, TrackedMarket, SystemStatus, MarketPrice

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Well-known US city coordinates for location extraction
# ---------------------------------------------------------------------------
_CITY_COORDS: dict[str, tuple[float, float]] = {
    "new york": (40.7128, -74.0060),
    "nyc": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "la": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298),
    "houston": (29.7604, -95.3698),
    "phoenix": (33.4484, -112.0740),
    "philadelphia": (39.9526, -75.1652),
    "san antonio": (29.4241, -98.4936),
    "san diego": (32.7157, -117.1611),
    "dallas": (32.7767, -96.7970),
    "san jose": (37.3382, -121.8863),
    "austin": (30.2672, -97.7431),
    "jacksonville": (30.3322, -81.6557),
    "san francisco": (37.7749, -122.4194),
    "seattle": (47.6062, -122.3321),
    "denver": (39.7392, -104.9903),
    "washington": (38.9072, -77.0369),
    "dc": (38.9072, -77.0369),
    "nashville": (36.1627, -86.7816),
    "miami": (25.7617, -80.1918),
    "atlanta": (33.7490, -84.3880),
    "boston": (42.3601, -71.0589),
    "minneapolis": (44.9778, -93.2650),
    "detroit": (42.3314, -83.0458),
    "portland": (45.5152, -122.6784),
    "las vegas": (36.1699, -115.1398),
    "memphis": (35.1495, -90.0490),
    "louisville": (38.2527, -85.7585),
    "baltimore": (39.2904, -76.6122),
    "milwaukee": (43.0389, -87.9065),
    "albuquerque": (35.0844, -106.6504),
    "tucson": (32.2226, -110.9747),
    "fresno": (36.7378, -119.7871),
    "sacramento": (38.5816, -121.4944),
    "kansas city": (39.0997, -94.5786),
    "mesa": (33.4152, -111.8315),
    "omaha": (41.2565, -95.9345),
    "raleigh": (35.7796, -78.6382),
    "cleveland": (41.4993, -81.6944),
    "tampa": (27.9506, -82.4572),
    "new orleans": (29.9511, -90.0715),
    "pittsburgh": (40.4406, -79.9959),
    "st. louis": (38.6270, -90.1994),
    "st louis": (38.6270, -90.1994),
    "orlando": (28.5383, -81.3792),
    "honolulu": (21.3069, -157.8583),
    "anchorage": (61.2181, -149.9003),
}

# US state code to full name (for NWS alerts)
_STATE_CODES: dict[str, str] = {
    "al": "AL", "ak": "AK", "az": "AZ", "ar": "AR", "ca": "CA",
    "co": "CO", "ct": "CT", "de": "DE", "fl": "FL", "ga": "GA",
    "hi": "HI", "id": "ID", "il": "IL", "in": "IN", "ia": "IA",
    "ks": "KS", "ky": "KY", "la": "LA", "me": "ME", "md": "MD",
    "ma": "MA", "mi": "MI", "mn": "MN", "ms": "MS", "mo": "MO",
    "mt": "MT", "ne": "NE", "nv": "NV", "nh": "NH", "nj": "NJ",
    "nm": "NM", "ny": "NY", "nc": "NC", "nd": "ND", "oh": "OH",
    "ok": "OK", "or": "OR", "pa": "PA", "ri": "RI", "sc": "SC",
    "sd": "SD", "tn": "TN", "tx": "TX", "ut": "UT", "vt": "VT",
    "va": "VA", "wa": "WA", "wv": "WV", "wi": "WI", "wy": "WY",
    "dc": "DC",
    # Also accept uppercase versions directly
    "AL": "AL", "AK": "AK", "AZ": "AZ", "AR": "AR", "CA": "CA",
    "CO": "CO", "CT": "CT", "DE": "DE", "FL": "FL", "GA": "GA",
    "HI": "HI", "ID": "ID", "IL": "IL", "IN": "IN", "IA": "IA",
    "KS": "KS", "KY": "KY", "LA": "LA", "ME": "ME", "MD": "MD",
    "MA": "MA", "MI": "MI", "MN": "MN", "MS": "MS", "MO": "MO",
    "MT": "MT", "NE": "NE", "NV": "NV", "NH": "NH", "NJ": "NJ",
    "NM": "NM", "NY": "NY", "NC": "NC", "ND": "ND", "OH": "OH",
    "OK": "OK", "OR": "OR", "PA": "PA", "RI": "RI", "SC": "SC",
    "SD": "SD", "TN": "TN", "TX": "TX", "UT": "UT", "VT": "VT",
    "VA": "VA", "WA": "WA", "WV": "WV", "WI": "WI", "WY": "WY",
    "DC": "DC",
}

# Map well-known cities to state codes for NWS alerts
_CITY_TO_STATE: dict[str, str] = {
    "new york": "NY", "nyc": "NY", "los angeles": "CA", "la": "CA",
    "chicago": "IL", "houston": "TX", "phoenix": "AZ",
    "philadelphia": "PA", "san antonio": "TX", "san diego": "CA",
    "dallas": "TX", "san jose": "CA", "austin": "TX",
    "jacksonville": "FL", "san francisco": "CA", "seattle": "WA",
    "denver": "CO", "washington": "DC", "dc": "DC",
    "nashville": "TN", "miami": "FL", "atlanta": "GA", "boston": "MA",
    "minneapolis": "MN", "detroit": "MI", "portland": "OR",
    "las vegas": "NV", "memphis": "TN", "louisville": "KY",
    "baltimore": "MD", "milwaukee": "WI", "albuquerque": "NM",
    "tucson": "AZ", "fresno": "CA", "sacramento": "CA",
    "kansas city": "MO", "mesa": "AZ", "omaha": "NE",
    "raleigh": "NC", "cleveland": "OH", "tampa": "FL",
    "new orleans": "LA", "pittsburgh": "PA", "st. louis": "MO",
    "st louis": "MO", "orlando": "FL", "honolulu": "HI",
    "anchorage": "AK",
}


def _extract_location(text: str) -> tuple[float, float, str | None] | None:
    """
    Extract geographic coordinates and an optional state code from text.

    Tries the following strategies in order:
        1. Explicit lat/lon coordinates like ``40.71,-74.01``.
        2. Known city names from the lookup table.
        3. Two-letter US state codes (centroid approximation).

    Args:
        text: The event name or market title to parse.

    Returns:
        A tuple of (latitude, longitude, state_code_or_None) or None if
        no location could be identified.
    """
    if not text:
        return None

    # Strategy 1: explicit coordinates  e.g. "40.71, -74.01"
    coord_match = re.search(
        r'(-?\d{1,3}\.\d+)\s*[,/]\s*(-?\d{1,3}\.\d+)', text
    )
    if coord_match:
        lat = float(coord_match.group(1))
        lon = float(coord_match.group(2))
        return (lat, lon, None)

    lower = text.lower()

    # Strategy 2: known city name
    for city, (lat, lon) in _CITY_COORDS.items():
        if city in lower:
            state = _CITY_TO_STATE.get(city)
            return (lat, lon, state)

    # Strategy 3: two-letter state code (use geographic centre)
    state_match = re.search(r'\b([A-Z]{2})\b', text)
    if state_match:
        code = state_match.group(1)
        if code in _STATE_CODES:
            # Use a rough state centroid -- Washington DC as generic fallback
            return (38.9, -77.0, code)

    return None


def _extract_threshold(text: str) -> tuple[str, float] | None:
    """
    Extract a weather threshold from a market title.

    Recognises patterns like:
      - "Will temp exceed 100 F?"
      - "temperature above 95"
      - "precipitation over 2 inches"
      - "wind speed exceed 50 mph"

    Args:
        text: The event name or market title.

    Returns:
        A tuple of (metric, threshold_value) or None if no threshold is
        found.  metric is one of 'temperature', 'precipitation', 'wind'.
    """
    if not text:
        return None

    lower = text.lower()

    # Temperature patterns
    temp_match = re.search(
        r'(?:temp(?:erature)?|high|degrees?)\s*'
        r'(?:exceed|above|over|greater than|>|reach)\s*'
        r'(\d+(?:\.\d+)?)',
        lower,
    )
    if temp_match:
        return ("temperature", float(temp_match.group(1)))

    # Precipitation patterns
    precip_match = re.search(
        r'(?:rain(?:fall)?|precip(?:itation)?|snow(?:fall)?)\s*'
        r'(?:exceed|above|over|greater than|>)\s*'
        r'(\d+(?:\.\d+)?)',
        lower,
    )
    if precip_match:
        return ("precipitation", float(precip_match.group(1)))

    # Wind patterns
    wind_match = re.search(
        r'(?:wind(?:\s*speed)?|gust)\s*'
        r'(?:exceed|above|over|greater than|>)\s*'
        r'(\d+(?:\.\d+)?)',
        lower,
    )
    if wind_match:
        return ("wind", float(wind_match.group(1)))

    return None


def _norm_cdf(x: float) -> float:
    """
    Compute the cumulative distribution function of the standard normal.

    Uses the math.erfc approximation so scipy is not a hard dependency
    at import time.

    Args:
        x: The z-score.

    Returns:
        P(Z <= x) for Z ~ N(0,1).
    """
    return 0.5 * math.erfc(-x / math.sqrt(2))


class WeatherClient:
    """
    Async weather-data client for ArbitrageIQ.

    Enriches weather-related TrackedMarkets with forecast data, historical
    statistics, and derived probabilities.  Data sources:

    - Open-Meteo forecast API (temperature, precipitation, wind)
    - Open-Meteo historical archive (30-day lookback for z-score model)
    - NWS active alerts API
    """

    def __init__(self) -> None:
        """Initialise with API URLs from constants."""
        self.forecast_url = OPEN_METEO_URL
        self.historical_url = OPEN_METEO_HISTORICAL_URL
        self.nws_url = NWS_API_URL

    def _update_system_status(self, error: str | None = None) -> None:
        """
        Persist weather ingestor health information to SystemStatus.

        Args:
            error: If not None, the error message to record.
        """
        try:
            db = SessionLocal()
            try:
                status = (
                    db.query(SystemStatus)
                    .filter(SystemStatus.source == "weather")
                    .first()
                )
                if not status:
                    status = SystemStatus(source="weather", component="weather")
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
                f"Could not update SystemStatus for weather: {exc}"
            )

    async def _fetch_forecast(
        self,
        client: httpx.AsyncClient,
        lat: float,
        lon: float,
    ) -> dict[str, Any]:
        """
        Fetch a 7-day daily forecast from Open-Meteo.

        Requests temperature_2m_max, temperature_2m_min, precipitation_sum,
        and windspeed_10m_max in imperial units.

        Args:
            client: An active httpx.AsyncClient.
            lat: Latitude.
            lon: Longitude.

        Returns:
            The parsed JSON response dict, or an empty dict on failure.
        """
        try:
            resp = await client.get(
                self.forecast_url,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "daily": (
                        "temperature_2m_max,temperature_2m_min,"
                        "precipitation_sum,windspeed_10m_max"
                    ),
                    "temperature_unit": "fahrenheit",
                    "windspeed_unit": "mph",
                    "precipitation_unit": "inch",
                    "timezone": "America/New_York",
                    "forecast_days": 7,
                },
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error(f"Open-Meteo forecast request failed: {exc}")
            return {}

    async def _fetch_historical(
        self,
        client: httpx.AsyncClient,
        lat: float,
        lon: float,
    ) -> dict[str, Any]:
        """
        Fetch 30 days of historical weather from Open-Meteo archive API.

        Used to compute the standard deviation (sigma) for the z-score
        probability model.

        Args:
            client: An active httpx.AsyncClient.
            lat: Latitude.
            lon: Longitude.

        Returns:
            The parsed JSON response dict, or an empty dict on failure.
        """
        end_date = datetime.now(timezone.utc).date() - timedelta(days=1)
        start_date = end_date - timedelta(days=30)

        try:
            resp = await client.get(
                self.historical_url,
                params={
                    "latitude": lat,
                    "longitude": lon,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "daily": (
                        "temperature_2m_max,temperature_2m_min,"
                        "precipitation_sum,windspeed_10m_max"
                    ),
                    "temperature_unit": "fahrenheit",
                    "windspeed_unit": "mph",
                    "precipitation_unit": "inch",
                    "timezone": "America/New_York",
                },
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.error(f"Open-Meteo historical request failed: {exc}")
            return {}

    async def _fetch_nws_alerts(
        self,
        client: httpx.AsyncClient,
        state: str,
    ) -> list[dict]:
        """
        Fetch active NWS weather alerts for a US state.

        Args:
            client: An active httpx.AsyncClient.
            state: Two-letter US state code (e.g. 'TX').

        Returns:
            A list of alert feature dicts from the GeoJSON response, or
            an empty list on failure.
        """
        try:
            resp = await client.get(
                f"{self.nws_url}/alerts/active",
                params={"area": state},
                headers={"User-Agent": "ArbitrageIQ/1.0 (weather@arbitrageiq.com)"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("features", [])
        except Exception as exc:
            logger.warning(f"NWS alerts request failed for {state}: {exc}")
            return []

    def _compute_stats(
        self, values: list[float | None]
    ) -> tuple[float, float]:
        """
        Compute mean and standard deviation from a list of values.

        None values are filtered out.  If fewer than 2 valid values remain,
        sigma defaults to 1.0 to avoid division by zero.

        Args:
            values: Raw daily observations (may contain None).

        Returns:
            A (mean, std_dev) tuple.
        """
        clean = [v for v in values if v is not None]
        if len(clean) < 2:
            return (clean[0] if clean else 0.0, 1.0)

        mean = sum(clean) / len(clean)
        variance = sum((x - mean) ** 2 for x in clean) / (len(clean) - 1)
        std = math.sqrt(variance) if variance > 0 else 1.0
        return (mean, std)

    def _threshold_probability(
        self,
        forecast_value: float,
        sigma: float,
        threshold: float,
        direction: str = "exceed",
    ) -> float:
        """
        Compute probability that the actual value exceeds (or falls below) a threshold.

        Uses a normal distribution centred on the forecast with the given
        sigma (historical standard deviation).

        For 'exceed': P(X > threshold) = 1 - CDF((threshold - forecast) / sigma)
        For 'below':  P(X < threshold) = CDF((threshold - forecast) / sigma)

        Args:
            forecast_value: The point forecast.
            sigma: Standard deviation from historical data.
            threshold: The threshold to compare against.
            direction: Either 'exceed' or 'below'.

        Returns:
            A probability between 0.0 and 1.0.
        """
        if sigma <= 0:
            sigma = 1.0

        z = (threshold - forecast_value) / sigma

        if direction == "exceed":
            return 1.0 - _norm_cdf(z)
        else:
            return _norm_cdf(z)

    async def _fetch_wttr_forecast(
        self,
        client: httpx.AsyncClient,
        city_name: str,
    ) -> dict[str, Any] | None:
        """
        Fetch a lightweight forecast from wttr.in (free, no API key).
        Used as a cross-reference for Open-Meteo data to strengthen
        discrepancy confidence.
        """
        try:
            resp = await client.get(
                f"https://wttr.in/{city_name}?format=j1",
                timeout=10,
                headers={"User-Agent": "ArbitrageIQ/1.0"},
            )
            resp.raise_for_status()
            data = resp.json()
            weather = data.get("weather", [])
            if weather:
                day = weather[0]
                return {
                    "temp_max_f": float(day.get("maxtempF", 0)),
                    "temp_min_f": float(day.get("mintempF", 0)),
                    "source": "wttr.in",
                }
        except Exception as exc:
            logger.debug(f"wttr.in forecast failed for {city_name}: {exc}")
        return None

    async def fetch(self) -> list[dict[str, Any]]:
        """
        Process all weather-related TrackedMarkets and return enriched results.

        For each active TrackedMarket with category 'weather':
            1. Extract a location from the market title.
            2. Fetch the Open-Meteo 7-day forecast.
            3. Fetch 30 days of Open-Meteo historical data.
            4. Compute historical mean and standard deviation.
            5. If a threshold is detected in the title, compute a z-score
               probability.
            6. Fetch NWS active alerts for the state (if identifiable).
            7. Return a structured result dict with forecast, stats,
               probability, and alerts.

        Returns:
            A list of dicts, each containing: market_id, market_title,
            location, forecast, historical_stats, derived_probability,
            nws_alerts, timestamp.
        """
        results: list[dict[str, Any]] = []

        # Load weather-related tracked markets from DB
        try:
            db = SessionLocal()
            try:
                tracked = (
                    db.query(TrackedMarket)
                    .filter(
                        TrackedMarket.category == "weather",
                        TrackedMarket.is_active.is_(True),
                    )
                    .all()
                )
                # Detach from session so we can use them after close
                market_data = [
                    {
                        "market_id": t.market_id,
                        "market_title": t.market_title or "",
                        "source": t.source,
                    }
                    for t in tracked
                ]
            finally:
                db.close()
        except Exception as exc:
            logger.error(f"Failed to load weather tracked markets: {exc}")
            self._update_system_status(error=str(exc))
            return []

        if not market_data:
            logger.info("No weather-related tracked markets found")
            return []

        logger.info(
            f"Processing {len(market_data)} weather-related tracked markets"
        )

        async with httpx.AsyncClient(timeout=30) as client:
            for mkt in market_data:
                title = mkt["market_title"]
                market_id = mkt["market_id"]

                # Step 1: Extract location
                location = _extract_location(title)
                if location is None:
                    logger.debug(
                        f"Could not extract location from: {title!r}"
                    )
                    continue

                lat, lon, state = location

                # Step 2: Fetch forecast
                forecast_data = await self._fetch_forecast(client, lat, lon)
                daily = forecast_data.get("daily", {})

                temp_max_list = daily.get("temperature_2m_max", [])
                temp_min_list = daily.get("temperature_2m_min", [])
                precip_list = daily.get("precipitation_sum", [])
                wind_list = daily.get("windspeed_10m_max", [])
                dates = daily.get("time", [])

                # Build a clean forecast summary
                forecast_summary: list[dict] = []
                for i in range(len(dates)):
                    forecast_summary.append(
                        {
                            "date": dates[i] if i < len(dates) else None,
                            "temp_max_f": (
                                temp_max_list[i]
                                if i < len(temp_max_list)
                                else None
                            ),
                            "temp_min_f": (
                                temp_min_list[i]
                                if i < len(temp_min_list)
                                else None
                            ),
                            "precip_inches": (
                                precip_list[i]
                                if i < len(precip_list)
                                else None
                            ),
                            "wind_max_mph": (
                                wind_list[i]
                                if i < len(wind_list)
                                else None
                            ),
                        }
                    )

                # Step 2b: Cross-reference with wttr.in (free, no key)
                city_name = None
                for city in _CITY_COORDS:
                    if city in title.lower():
                        city_name = city.replace(" ", "+")
                        break
                wttr_data = None
                if city_name:
                    wttr_data = await self._fetch_wttr_forecast(client, city_name)

                # Step 3: Fetch historical data
                hist_data = await self._fetch_historical(client, lat, lon)
                hist_daily = hist_data.get("daily", {})

                hist_temp_max = hist_daily.get("temperature_2m_max", [])
                hist_temp_min = hist_daily.get("temperature_2m_min", [])
                hist_precip = hist_daily.get("precipitation_sum", [])
                hist_wind = hist_daily.get("windspeed_10m_max", [])

                # Step 4: Compute historical statistics
                temp_max_mean, temp_max_std = self._compute_stats(hist_temp_max)
                temp_min_mean, temp_min_std = self._compute_stats(hist_temp_min)
                precip_mean, precip_std = self._compute_stats(hist_precip)
                wind_mean, wind_std = self._compute_stats(hist_wind)

                historical_stats = {
                    "temp_max": {
                        "mean": round(temp_max_mean, 2),
                        "std": round(temp_max_std, 2),
                    },
                    "temp_min": {
                        "mean": round(temp_min_mean, 2),
                        "std": round(temp_min_std, 2),
                    },
                    "precipitation": {
                        "mean": round(precip_mean, 4),
                        "std": round(precip_std, 4),
                    },
                    "wind_max": {
                        "mean": round(wind_mean, 2),
                        "std": round(wind_std, 2),
                    },
                }

                # Step 5: Derive threshold probability if applicable
                derived_probability: float | None = None
                threshold_info = _extract_threshold(title)

                if threshold_info and forecast_summary:
                    metric, threshold_val = threshold_info
                    # Use first forecast day as the point estimate
                    first_day = forecast_summary[0]

                    if metric == "temperature":
                        forecast_val = first_day.get("temp_max_f")
                        sigma = temp_max_std
                    elif metric == "precipitation":
                        forecast_val = first_day.get("precip_inches")
                        sigma = precip_std
                    elif metric == "wind":
                        forecast_val = first_day.get("wind_max_mph")
                        sigma = wind_std
                    else:
                        forecast_val = None
                        sigma = 1.0

                    if forecast_val is not None:
                        derived_probability = self._threshold_probability(
                            forecast_value=forecast_val,
                            sigma=sigma,
                            threshold=threshold_val,
                            direction="exceed",
                        )
                        derived_probability = round(derived_probability, 4)

                # Step 6: NWS alerts
                nws_alerts: list[dict] = []
                if state:
                    raw_alerts = await self._fetch_nws_alerts(client, state)
                    for alert in raw_alerts:
                        props = alert.get("properties", {})
                        nws_alerts.append(
                            {
                                "event": props.get("event", ""),
                                "headline": props.get("headline", ""),
                                "severity": props.get("severity", ""),
                                "certainty": props.get("certainty", ""),
                                "effective": props.get("effective", ""),
                                "expires": props.get("expires", ""),
                                "description": (
                                    props.get("description", "")[:500]
                                ),
                            }
                        )

                result = {
                    "market_id": market_id,
                    "market_title": title,
                    "source": mkt["source"],
                    "location": {
                        "latitude": lat,
                        "longitude": lon,
                        "state": state,
                    },
                    "forecast": forecast_summary,
                    "historical_stats": historical_stats,
                    "derived_probability": derived_probability,
                    "threshold_info": (
                        {
                            "metric": threshold_info[0],
                            "threshold": threshold_info[1],
                        }
                        if threshold_info
                        else None
                    ),
                    "cross_reference": wttr_data,
                    "nws_alerts": nws_alerts,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                results.append(result)
                logger.info(
                    f"Weather data for {market_id}: "
                    f"prob={derived_probability}, "
                    f"alerts={len(nws_alerts)}"
                )

        # Persist weather-derived probabilities as MarketPrice rows
        # so the discrepancy engine can compare them against prediction markets
        if results:
            try:
                db = SessionLocal()
                try:
                    # Deactivate old weather data
                    db.query(MarketPrice).filter(
                        MarketPrice.source == "weather",
                        MarketPrice.is_active == True,  # noqa: E712
                    ).update({"is_active": False})

                    for r in results:
                        if r.get("derived_probability") is not None:
                            db.add(MarketPrice(
                                source="weather",
                                market_id=r["market_id"],
                                event_name=r["market_title"],
                                market_title=r["market_title"],
                                outcome="yes",
                                implied_probability=r["derived_probability"],
                                category="weather",
                                yes_price=r["derived_probability"],
                                no_price=1.0 - r["derived_probability"],
                                metadata_={
                                    "forecast": r.get("forecast", [])[:2],
                                    "historical_stats": r.get("historical_stats"),
                                    "threshold_info": r.get("threshold_info"),
                                    "nws_alerts_count": len(r.get("nws_alerts", [])),
                                },
                                is_active=True,
                            ))

                    db.commit()
                    logger.info(f"Saved {len(results)} weather data points to DB")
                finally:
                    db.close()
            except Exception as exc:
                logger.error(f"Failed to save weather data to DB: {exc}")

            self._update_system_status()
        else:
            logger.info("No weather results produced (no valid locations)")

        return results
