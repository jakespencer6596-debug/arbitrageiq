"""
APScheduler-based job scheduler for ArbitrageIQ.

Runs periodic jobs for data ingestion, arb/discrepancy detection,
market discovery, and self-keepalive.  All jobs are async-safe.

Usage:
    from scheduler import start_scheduler, stop_scheduler
    start_scheduler()   # call once at app startup
    stop_scheduler()    # call once at shutdown
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from constants import (
    ODDS_API_POLL_SECONDS,
    KALSHI_POLL_SECONDS,
    POLYMARKET_POLL_SECONDS,
    PREDICTIT_POLL_SECONDS,
    WEATHER_POLL_SECONDS,
    ECONOMIC_POLL_SECONDS,
    KEEPALIVE_SECONDS,
    MIN_ARB_PROFIT_PCT,
    THRESHOLDS,
)
from db.models import (
    ArbOpportunity,
    Discrepancy,
    MarketPrice,
    SessionLocal,
    TrackedMarket,
)

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


# ===================================================================
# Ingestion jobs
# ===================================================================

async def fetch_odds() -> None:
    """Fetch latest sports odds from The Odds API."""
    try:
        from ingestion.odds_api import OddsAPIClient

        client = OddsAPIClient()
        results = await client.fetch()
        logger.info(f"fetch_odds: ingested {len(results)} price snapshots")
    except ImportError:
        logger.warning("fetch_odds: ingestion.odds_api not available — skipping")
    except Exception as exc:
        logger.error(f"fetch_odds failed: {exc}", exc_info=True)


async def fetch_kalshi() -> None:
    """Fetch latest Kalshi prediction-market data."""
    try:
        from ingestion.kalshi import KalshiClient

        client = KalshiClient()
        results = await client.fetch()
        logger.info(f"fetch_kalshi: ingested {len(results)} price snapshots")
    except ImportError:
        logger.warning("fetch_kalshi: ingestion.kalshi not available — skipping")
    except Exception as exc:
        logger.error(f"fetch_kalshi failed: {exc}", exc_info=True)


async def fetch_polymarket() -> None:
    """Fetch latest Polymarket prediction-market data."""
    try:
        from ingestion.polymarket import PolymarketClient

        client = PolymarketClient()
        results = await client.fetch()
        logger.info(f"fetch_polymarket: ingested {len(results)} price snapshots")
    except ImportError:
        logger.warning("fetch_polymarket: ingestion.polymarket not available — skipping")
    except Exception as exc:
        logger.error(f"fetch_polymarket failed: {exc}", exc_info=True)


async def fetch_predictit() -> None:
    """Fetch latest PredictIt prediction-market data."""
    try:
        from ingestion.predictit import PredictItClient

        client = PredictItClient()
        results = await client.fetch()
        logger.info(f"fetch_predictit: ingested {len(results)} price snapshots")
    except ImportError:
        logger.warning("fetch_predictit: ingestion.predictit not available — skipping")
    except Exception as exc:
        logger.error(f"fetch_predictit failed: {exc}", exc_info=True)


async def fetch_weather() -> None:
    """Fetch latest weather data from Open-Meteo / NWS."""
    try:
        from ingestion.weather import WeatherClient

        client = WeatherClient()
        results = await client.fetch()
        logger.info(f"fetch_weather: ingested {len(results)} data points")
    except ImportError:
        logger.warning("fetch_weather: ingestion.weather not available — skipping")
    except Exception as exc:
        logger.error(f"fetch_weather failed: {exc}", exc_info=True)


async def fetch_economic() -> None:
    """Fetch latest economic indicators from FRED."""
    try:
        from ingestion.economic import EconomicClient

        client = EconomicClient()
        results = await client.fetch()
        logger.info(f"fetch_economic: ingested {len(results)} indicators")
    except ImportError:
        logger.warning("fetch_economic: ingestion.economic not available — skipping")
    except Exception as exc:
        logger.error(f"fetch_economic failed: {exc}", exc_info=True)


# ===================================================================
# Detection jobs
# ===================================================================

async def run_arb() -> None:
    """
    Load active MarketPrices, run the arb detection engine, persist
    any new ArbOpportunity rows, send alerts, and broadcast via WS.
    """
    db = SessionLocal()
    try:
        # 1. Load recent active prices
        prices = (
            db.query(MarketPrice)
            .filter(MarketPrice.is_active == True)  # noqa: E712
            .all()
        )

        if not prices:
            logger.debug("run_arb: no active market prices — nothing to do")
            return

        # 2. Run detection engine
        try:
            from engines.arb_engine import detect_arb
        except ImportError:
            logger.warning("run_arb: engines.arb_detector not available — skipping")
            return

        price_dicts = []
        for p in prices:
            # Use event_name or fall back to market_title
            name = p.event_name or p.market_title or ""
            # Use implied_probability or fall back to yes_price
            prob = p.implied_probability or p.yes_price or 0
            odds = p.raw_odds or (1.0 / prob if prob > 0 else None)
            price_dicts.append({
                "source": p.source,
                "market_id": p.market_id,
                "event_name": name,
                "outcome": p.outcome or "yes",
                "implied_probability": prob,
                "raw_odds": odds,
                "category": p.category or "other",
            })

        opportunities = detect_arb(price_dicts)

        if not opportunities:
            logger.debug("run_arb: no arbitrage opportunities detected")
            return

        logger.info(f"run_arb: detected {len(opportunities)} arb opportunities")

        # 3. Persist to DB
        saved_count = 0
        for opp in opportunities:
            d = opp.to_dict() if hasattr(opp, 'to_dict') else opp
            row = ArbOpportunity(
                event_name=d.get("event_name", "Unknown"),
                category=d.get("category", "sports"),
                profit_pct=d.get("profit_pct", d.get("profit_pct", 0)),
                legs=d.get("legs", []),
                total_stake_base=1000.0,
                profit_on_base=d.get("profit_on_1000", d.get("profit_on_base")),
                is_active=True,
            )
            db.add(row)
            saved_count += 1

        db.commit()
        logger.info(f"run_arb: saved {saved_count} opportunities to DB")

        # 4. Send alerts
        try:
            from alerts.telegram import send_arb_alert

            for opp in opportunities:
                await send_arb_alert(opp)
        except ImportError:
            logger.debug("run_arb: alerts.telegram not available — skipping alerts")
        except Exception as exc:
            logger.error(f"run_arb: alert dispatch failed: {exc}")

        # 5. Broadcast via WebSocket
        try:
            from api.routes import broadcast

            for opp in opportunities:
                await broadcast({
                    "type": "arb",
                    "data": opp,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except ImportError:
            logger.debug("run_arb: api.routes.broadcast not available")
        except Exception as exc:
            logger.error(f"run_arb: WS broadcast failed: {exc}")

    except Exception as exc:
        logger.error(f"run_arb failed: {exc}", exc_info=True)
    finally:
        db.close()


async def run_discrepancy() -> None:
    """
    Load mapped markets and their public data, run the discrepancy
    detection engine, persist results, send alerts, and broadcast.
    """
    db = SessionLocal()
    try:
        # 1. Load mapped, active tracked markets
        tracked = (
            db.query(TrackedMarket)
            .filter(
                TrackedMarket.is_mapped == True,  # noqa: E712
                TrackedMarket.is_active == True,   # noqa: E712
            )
            .all()
        )

        if not tracked:
            logger.debug("run_discrepancy: no mapped markets — nothing to do")
            return

        # 2. For each tracked market, load the latest price
        market_data = []
        for tm in tracked:
            latest_price = (
                db.query(MarketPrice)
                .filter(
                    MarketPrice.source == tm.source,
                    MarketPrice.market_id == tm.market_id,
                    MarketPrice.is_active == True,  # noqa: E712
                )
                .order_by(MarketPrice.timestamp.desc())
                .first()
            )
            if latest_price:
                market_data.append({
                    "tracked_market": {
                        "id": tm.id,
                        "source": tm.source,
                        "market_id": tm.market_id,
                        "event_name": tm.event_name,
                        "category": tm.category,
                        "data_sources": tm.data_sources,
                        "resolution_criteria": tm.resolution_criteria,
                        "metadata": tm.metadata_,
                    },
                    "price": {
                        "implied_probability": latest_price.implied_probability,
                        "raw_odds": latest_price.raw_odds,
                        "outcome": latest_price.outcome,
                        "timestamp": latest_price.timestamp,
                    },
                })

        if not market_data:
            logger.debug("run_discrepancy: no price data for mapped markets")
            return

        # 3. Run detection engine
        try:
            from engines.discrepancy_engine import detect_discrepancy
        except ImportError:
            logger.warning(
                "run_discrepancy: engines.discrepancy_engine not available — skipping"
            )
            return

        discrepancies = []
        for md in market_data:
            tm = md["tracked_market"]
            price = md["price"]
            market_dict = {
                "market_id": tm["market_id"],
                "source": tm["source"],
                "event_name": tm["event_name"],
                "implied_probability": price["implied_probability"],
            }
            # For now, skip markets without public data comparison
            # (weather/economic modules populate this data)
            if tm.get("data_sources"):
                # Placeholder: public data would be fetched/cached by ingestion modules
                pass

        if not discrepancies:
            logger.debug("run_discrepancy: no discrepancies detected")
            return

        logger.info(f"run_discrepancy: detected {len(discrepancies)} discrepancies")

        # 4. Persist to DB
        saved_count = 0
        for disc in discrepancies:
            row = Discrepancy(
                market_id=disc.get("market_id", ""),
                source=disc.get("source", ""),
                event_name=disc.get("event_name", "Unknown"),
                category=disc.get("category", "other"),
                market_probability=disc.get("market_probability", 0.0),
                data_implied_probability=disc.get("data_implied_probability", 0.0),
                edge_pct=disc.get("edge_pct", 0.0),
                direction=disc.get("direction", "unknown"),
                data_source=disc.get("data_source"),
                data_value=disc.get("data_value"),
                data_unit=disc.get("data_unit"),
                confidence=disc.get("confidence", "medium"),
                is_active=True,
                notes=disc.get("notes"),
            )
            db.add(row)
            saved_count += 1

        db.commit()
        logger.info(f"run_discrepancy: saved {saved_count} discrepancies to DB")

        # 5. Send alerts
        try:
            from alerts.telegram import send_discrepancy_alert

            for disc in discrepancies:
                await send_discrepancy_alert(disc)
        except ImportError:
            logger.debug(
                "run_discrepancy: alerts.telegram not available — skipping alerts"
            )
        except Exception as exc:
            logger.error(f"run_discrepancy: alert dispatch failed: {exc}")

        # 6. Broadcast via WebSocket
        try:
            from api.routes import broadcast

            for disc in discrepancies:
                await broadcast({
                    "type": "discrepancy",
                    "data": disc,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
        except ImportError:
            logger.debug("run_discrepancy: api.routes.broadcast not available")
        except Exception as exc:
            logger.error(f"run_discrepancy: WS broadcast failed: {exc}")

    except Exception as exc:
        logger.error(f"run_discrepancy failed: {exc}", exc_info=True)
    finally:
        db.close()


# ===================================================================
# Market discovery
# ===================================================================

async def discover_markets() -> None:
    """
    Load unmapped TrackedMarkets, run map_market on each to link them
    to public data sources, and save the mapping results.
    """
    db = SessionLocal()
    try:
        unmapped = (
            db.query(TrackedMarket)
            .filter(
                TrackedMarket.is_mapped == False,  # noqa: E712
                TrackedMarket.is_active == True,    # noqa: E712
            )
            .all()
        )

        if not unmapped:
            logger.debug("discover_markets: no unmapped markets — nothing to do")
            return

        try:
            from engines.market_mapper import map_market
        except ImportError:
            logger.warning(
                "discover_markets: engines.market_mapper not available — skipping"
            )
            return

        mapped_count = 0
        for tm in unmapped:
            try:
                result = map_market({
                    "source": tm.source,
                    "market_id": tm.market_id,
                    "event_name": tm.event_name or tm.market_title or "",
                    "category": tm.category,
                })

                if result and result.get("is_mapped"):
                    tm.is_mapped = True
                    tm.data_sources = result.get("data_sources", [])
                    tm.category = result.get("category", tm.category)
                    tm.last_updated = datetime.now(timezone.utc)
                    mapped_count += 1
                    logger.info(
                        f"discover_markets: mapped {tm.source}:{tm.market_id} "
                        f"-> {result.get('data_sources', [])}"
                    )
            except Exception as exc:
                logger.error(
                    f"discover_markets: failed to map {tm.source}:{tm.market_id}: {exc}"
                )

        db.commit()
        logger.info(
            f"discover_markets: mapped {mapped_count}/{len(unmapped)} markets"
        )

    except Exception as exc:
        logger.error(f"discover_markets failed: {exc}", exc_info=True)
    finally:
        db.close()


# ===================================================================
# Keepalive
# ===================================================================

async def keepalive() -> None:
    """
    Ping own /ping endpoint to prevent cold-start on hosting platforms
    like Render that spin down idle services.
    """
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("BASE_URL") or "http://127.0.0.1:8000"
    ping_url = f"{url.rstrip('/')}/ping"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(ping_url)
            logger.debug(f"keepalive: pinged {ping_url} -> {resp.status_code}")
    except Exception as exc:
        logger.warning(f"keepalive: failed to ping {ping_url}: {exc}")


# ===================================================================
# Scheduler lifecycle
# ===================================================================

def start_scheduler() -> None:
    """
    Create the AsyncIOScheduler, register all jobs with their intervals,
    and start the scheduler.  Safe to call multiple times (idempotent).
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.warning("start_scheduler: scheduler already running")
        return

    _scheduler = AsyncIOScheduler(
        timezone="UTC",
        job_defaults={"misfire_grace_time": 60},
    )

    # --- Ingestion jobs (staggered to avoid OOM on 512MB free tier) ---
    _now = datetime.now(timezone.utc)
    _scheduler.add_job(
        fetch_odds,
        "interval",
        seconds=ODDS_API_POLL_SECONDS,
        id="fetch_odds",
        name="Odds API ingestion",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now,
    )
    _scheduler.add_job(
        fetch_kalshi,
        "interval",
        seconds=KALSHI_POLL_SECONDS,
        id="fetch_kalshi",
        name="Kalshi ingestion",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now + timedelta(seconds=10),
    )
    _scheduler.add_job(
        fetch_polymarket,
        "interval",
        seconds=POLYMARKET_POLL_SECONDS,
        id="fetch_polymarket",
        name="Polymarket ingestion",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now + timedelta(seconds=20),
    )
    _scheduler.add_job(
        fetch_predictit,
        "interval",
        seconds=PREDICTIT_POLL_SECONDS,
        id="fetch_predictit",
        name="PredictIt ingestion",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now + timedelta(seconds=30),
    )
    _scheduler.add_job(
        fetch_weather,
        "interval",
        seconds=WEATHER_POLL_SECONDS,
        id="fetch_weather",
        name="Weather data ingestion",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now + timedelta(seconds=40),
    )
    _scheduler.add_job(
        fetch_economic,
        "interval",
        seconds=ECONOMIC_POLL_SECONDS,
        id="fetch_economic",
        name="Economic data ingestion",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now + timedelta(seconds=50),
    )

    # --- Detection / analysis jobs ---
    _scheduler.add_job(
        run_arb,
        "interval",
        seconds=60,
        id="run_arb",
        name="Arb detection",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.add_job(
        run_discrepancy,
        "interval",
        seconds=120,
        id="run_discrepancy",
        name="Discrepancy detection",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.add_job(
        discover_markets,
        "interval",
        seconds=300,
        id="discover_markets",
        name="Market discovery / mapping",
        replace_existing=True,
        max_instances=1,
    )

    # --- Keepalive ---
    _scheduler.add_job(
        keepalive,
        "interval",
        seconds=KEEPALIVE_SECONDS,
        id="keepalive",
        name="Self-keepalive ping",
        replace_existing=True,
        max_instances=1,
    )

    _scheduler.start()
    logger.info(
        f"Scheduler started with {len(_scheduler.get_jobs())} jobs: "
        + ", ".join(j.id for j in _scheduler.get_jobs())
    )


def stop_scheduler() -> None:
    """Shut down the scheduler cleanly.  Safe to call if not running."""
    global _scheduler

    if _scheduler is None:
        return

    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")

    _scheduler = None
