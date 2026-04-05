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
    MANIFOLD_POLL_SECONDS,
    KEEPALIVE_SECONDS,
    PRICE_MAX_AGE_HOURS,
    MAX_PRICES_PER_SOURCE,
)
from db.models import (
    ArbOpportunity,
    Discrepancy,
    MarketPrice,
    SessionLocal,
    TrackedMarket,
    cleanup_old_data,
)

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


def _build_market_url(source: str, market_id: str, event_name: str,
                      raw_payload=None, metadata_=None) -> str:
    """Construct a direct URL to the market on its platform."""
    src = (source or "").lower().strip()
    q = event_name or ""

    if src == "polymarket":
        # Polymarket slugs from the API are market-level, not event-level,
        # so /event/{slug} often 404s. Use search instead for reliability.
        from urllib.parse import quote
        return f"https://polymarket.com/markets?_q={quote(q[:80])}"

    if src == "kalshi":
        # market_id is the ticker
        if market_id:
            return f"https://kalshi.com/markets/{market_id}"
        return "https://kalshi.com"

    if src == "predictit":
        # raw_payload may contain market_url
        if raw_payload and isinstance(raw_payload, dict):
            url = raw_payload.get("market_url")
            if url:
                return url
        # Extract numeric market ID from composite "marketid_contractid"
        parts = (market_id or "").split("_")
        if parts and parts[0].isdigit():
            return f"https://www.predictit.org/markets/detail/{parts[0]}"
        return "https://www.predictit.org/markets"

    if src == "manifold":
        if metadata_ and isinstance(metadata_, dict):
            url = metadata_.get("url")
            if url:
                return url
        from urllib.parse import quote
        return f"https://manifold.markets/search?q={quote(q[:80])}"

    # Sportsbooks — no deep links available, link to homepage
    sportsbooks = {
        "draftkings": "https://www.draftkings.com",
        "fanduel": "https://www.fanduel.com",
        "betmgm": "https://www.betmgm.com",
        "caesars": "https://www.caesars.com/sportsbook-and-casino",
        "pointsbet": "https://www.pointsbet.com",
        "betrivers": "https://www.betrivers.com",
        "bovada": "https://www.bovada.lv",
        "bet365": "https://www.bet365.com",
        "pinnacle": "https://www.pinnacle.com",
    }
    for name, url in sportsbooks.items():
        if name in src:
            return url

    return ""


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


async def fetch_manifold() -> None:
    """Fetch latest Manifold Markets prediction-market data."""
    try:
        from ingestion.manifold import ManifoldClient

        client = ManifoldClient()
        results = await client.fetch()
        logger.info(f"fetch_manifold: ingested {len(results)} price snapshots")
    except ImportError:
        logger.warning("fetch_manifold: ingestion.manifold not available — skipping")
    except Exception as exc:
        logger.error(f"fetch_manifold failed: {exc}", exc_info=True)


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
    # Skip if no category selected
    from constants import ACTIVE_CATEGORY
    if ACTIVE_CATEGORY is None:
        return

    db = SessionLocal()
    try:
        # 0. Deactivate ALL existing active arbs before inserting fresh ones
        # This prevents duplicate accumulation across detection cycles
        db.query(ArbOpportunity).filter(
            ArbOpportunity.is_active == True,  # noqa: E712
        ).update({"is_active": False})
        db.commit()

        # 1. Load recent active prices
        prices = (
            db.query(MarketPrice)
            .filter(MarketPrice.is_active == True)  # noqa: E712
            .all()
        )

        if not prices:
            logger.debug("run_arb: no active market prices — nothing to do")
            return

        # 2. Build price dicts for detection engines
        price_dicts = []
        for p in prices:
            # Use event_name or fall back to market_title
            name = p.event_name or p.market_title or ""
            # Use implied_probability or fall back to yes_price
            prob = p.implied_probability or p.yes_price or 0
            odds = p.raw_odds or (1.0 / prob if prob > 0 else None)
            # Build direct market URL from available data
            market_url = _build_market_url(
                p.source, p.market_id, name,
                raw_payload=p.raw_payload,
                metadata_=p.metadata_,
            )
            price_dicts.append({
                "source": p.source,
                "market_id": p.market_id,
                "event_name": name,
                "outcome": p.outcome or "yes",
                "implied_probability": prob,
                "raw_odds": odds,
                "category": p.category or "other",
                "market_url": market_url,
                "volume": p.volume or 0,
            })

        # Run both cross-platform arb detection AND overround detection
        try:
            from engines.arb_engine import detect_arb, detect_overround
        except ImportError:
            logger.warning("run_arb: engines.arb_engine not available — skipping")
            return

        cross_arbs = detect_arb(price_dicts)
        overround_arbs = detect_overround(price_dicts)
        opportunities = cross_arbs + overround_arbs

        if not opportunities:
            logger.debug("run_arb: no arbitrage opportunities detected")
            return

        logger.info(f"run_arb: detected {len(cross_arbs)} cross-platform + {len(overround_arbs)} overround arbs")

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

        # 4. Broadcast via WebSocket
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
    Compare prediction market prices against public data sources
    (FRED economic, Odds API sports) to find mispriced markets.
    """
    db = SessionLocal()
    try:
        try:
            from engines.discrepancy_engine import detect_discrepancy
        except ImportError:
            logger.warning("run_discrepancy: engine not available — skipping")
            return

        # Build a lookup of public-data implied probabilities by source
        # FRED/economic data is stored with source="fred", weather with "weather"
        public_sources = ["fred", "coingecko", "weather"]
        public_data: list = []
        for src in public_sources:
            prices = (
                db.query(MarketPrice)
                .filter(
                    MarketPrice.source == src,
                    MarketPrice.is_active == True,  # noqa: E712
                )
                .all()
            )
            public_data.extend(prices)

        # Load prediction market prices (Kalshi, Polymarket, PredictIt, Manifold)
        prediction_sources = ["kalshi", "polymarket", "predictit", "manifold"]
        pred_prices = (
            db.query(MarketPrice)
            .filter(
                MarketPrice.source.in_(prediction_sources),
                MarketPrice.is_active == True,  # noqa: E712
            )
            .all()
        )

        if not pred_prices:
            logger.debug("run_discrepancy: no prediction market prices")
            return

        from collections import defaultdict
        discrepancies = []
        seen = set()

        # ---------------------------------------------------------------
        # Part 1: Compare prediction markets vs PUBLIC DATA (weather, FRED)
        # This is the KEY feature — real data vs market prices
        # ---------------------------------------------------------------
        if public_data:
            # Use token-based matching to find prediction markets that
            # relate to public data points
            import re
            _stop = {"will", "the", "a", "an", "in", "of", "to", "for", "by",
                      "on", "at", "be", "is", "it", "and", "or", "not", "this",
                      "that", "with", "from", "yes", "no", "market", "price"}

            def _tokens(text):
                return set(re.findall(r'[a-z0-9]+', (text or "").lower())) - _stop

            for pub in public_data:
                pub_tokens = _tokens(pub.event_name)
                if len(pub_tokens) < 2:
                    continue
                pub_prob = pub.implied_probability
                if not pub_prob or pub_prob <= 0:
                    continue

                for pred in pred_prices:
                    pred_tokens = _tokens(pred.event_name)
                    if len(pred_tokens) < 2:
                        continue

                    shared = pub_tokens & pred_tokens
                    if len(shared) < 2:
                        continue

                    # Jaccard similarity
                    union = pub_tokens | pred_tokens
                    sim = len(shared) / len(union) if union else 0
                    if sim < 0.3:
                        continue

                    pred_prob = pred.implied_probability
                    if not pred_prob or pred_prob <= 0:
                        continue

                    edge = abs(pred_prob - pub_prob)
                    category = pub.category or pred.category or "other"
                    threshold = THRESHOLDS.get(category, 0.10)

                    if edge < threshold:
                        continue

                    disc_key = f"pub:{pub.source}:{pub.market_id}:{pred.source}:{pred.market_id}"
                    if disc_key in seen:
                        continue
                    seen.add(disc_key)

                    # Determine confidence based on source type
                    confidence = "high" if pub.source in ("fred", "weather") else "medium"
                    data_notes = f"Public data ({pub.source}) implies {pub_prob:.1%}, market at {pred_prob:.1%}"
                    if pub.metadata_ and isinstance(pub.metadata_, dict):
                        ti = pub.metadata_.get("threshold_info")
                        if ti:
                            data_notes += f" | {ti.get('metric', '')}: threshold {ti.get('threshold', '')}"

                    result = detect_discrepancy(
                        {
                            "market_id": pred.market_id,
                            "source": pred.source,
                            "event_name": pred.event_name or "",
                            "implied_probability": pred_prob,
                        },
                        {
                            "derived_probability": pub_prob,
                            "value": pub_prob,
                            "unit": "probability",
                            "source": pub.source,
                            "confidence": confidence,
                            "notes": data_notes,
                        },
                        category,
                    )
                    if result:
                        discrepancies.append(result.to_dict())

            logger.info(f"run_discrepancy: {len(discrepancies)} public-data discrepancies found")

        # ---------------------------------------------------------------
        # Part 2: Cross-platform prediction market comparison
        # ---------------------------------------------------------------
        event_groups: dict[str, list] = defaultdict(list)
        for p in pred_prices:
            key = (p.event_name or "").lower().strip()[:80]
            if key and p.implied_probability and p.implied_probability > 0:
                event_groups[key].append(p)

        for key, prices in event_groups.items():
            if len(prices) < 2:
                continue
            sources = set(p.source for p in prices)
            if len(sources) < 2:
                continue

            for i, p1 in enumerate(prices):
                for p2 in prices[i + 1:]:
                    if p1.source == p2.source:
                        continue
                    edge = abs(p1.implied_probability - p2.implied_probability)
                    category = p1.category or "other"
                    threshold = THRESHOLDS.get(category, 0.10)
                    if edge >= threshold:
                        disc_key = f"{p1.source}:{p1.market_id}:{p2.source}:{p2.market_id}"
                        if disc_key in seen:
                            continue
                        seen.add(disc_key)
                        direction = "BUY_YES" if p2.implied_probability > p1.implied_probability else "BUY_NO"
                        result = detect_discrepancy(
                            {
                                "market_id": p1.market_id,
                                "source": p1.source,
                                "event_name": p1.event_name or key,
                                "implied_probability": p1.implied_probability,
                            },
                            {
                                "derived_probability": p2.implied_probability,
                                "value": p2.implied_probability,
                                "unit": "probability",
                                "source": p2.source,
                                "confidence": "medium",
                                "notes": f"vs {p2.source} @ {p2.implied_probability:.2%}",
                            },
                            category,
                        )
                        if result:
                            discrepancies.append(result.to_dict())

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

async def run_cleanup() -> None:
    """Purge old DB rows to keep memory under control."""
    try:
        result = cleanup_old_data(
            max_age_hours=PRICE_MAX_AGE_HOURS,
            max_per_source=MAX_PRICES_PER_SOURCE,
        )
        logger.info(f"run_cleanup: purged {result}")
    except Exception as exc:
        logger.error(f"run_cleanup failed: {exc}", exc_info=True)


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

    # --- Ingestion jobs (heavily staggered to avoid OOM on 512 MB) ---
    # Each job starts at a different offset so only ONE runs at a time.
    _now = datetime.now(timezone.utc)
    _scheduler.add_job(
        fetch_odds,
        "interval",
        seconds=ODDS_API_POLL_SECONDS,
        id="fetch_odds",
        name="Odds API ingestion",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now + timedelta(seconds=10),
    )
    _scheduler.add_job(
        fetch_kalshi,
        "interval",
        seconds=KALSHI_POLL_SECONDS,
        id="fetch_kalshi",
        name="Kalshi ingestion",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now + timedelta(seconds=50),
    )
    _scheduler.add_job(
        fetch_polymarket,
        "interval",
        seconds=POLYMARKET_POLL_SECONDS,
        id="fetch_polymarket",
        name="Polymarket ingestion",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now + timedelta(seconds=90),
    )
    _scheduler.add_job(
        fetch_predictit,
        "interval",
        seconds=PREDICTIT_POLL_SECONDS,
        id="fetch_predictit",
        name="PredictIt ingestion",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now + timedelta(seconds=130),
    )
    _scheduler.add_job(
        fetch_manifold,
        "interval",
        seconds=MANIFOLD_POLL_SECONDS,
        id="fetch_manifold",
        name="Manifold Markets ingestion",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now + timedelta(seconds=170),
    )
    # --- Detection job (run after first data arrives) ---
    _scheduler.add_job(
        run_arb,
        "interval",
        seconds=120,
        id="run_arb",
        name="Arb detection",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now + timedelta(seconds=200),
    )

    # --- DB cleanup (critical for memory on 512 MB) ---
    _scheduler.add_job(
        run_cleanup,
        "interval",
        seconds=300,
        id="run_cleanup",
        name="DB cleanup",
        replace_existing=True,
        max_instances=1,
        next_run_time=_now + timedelta(seconds=90),
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
