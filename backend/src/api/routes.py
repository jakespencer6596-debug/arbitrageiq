"""
FastAPI router for ArbitrageIQ.

Endpoints:
  GET  /opportunities     — active arb + discrepancy data
  GET  /markets           — all tracked markets with status
  GET  /markets/unmapped  — tracked markets not yet mapped to public data
  GET  /health            — per-source component health
  GET  /stats             — aggregate dashboard counters
  POST /alerts/test       — fire a test Telegram alert
  WS   /ws/live           — real-time event stream for the frontend
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, Request
from sqlalchemy import func

import constants
from db.models import (
    ArbOpportunity,
    AlertLog,
    Discrepancy,
    MarketPrice,
    SessionLocal,
    SystemStatus,
    TrackedMarket,
    User,
)
from auth.auth import (
    hash_password, verify_password, create_token,
    get_current_user, get_optional_user,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@router.post("/auth/register")
async def register(body: dict):
    """Register a new user with email + password."""
    email = (body.get("email") or "").strip().lower()
    password = body.get("password", "")

    if not email or "@" not in email:
        return {"error": "Valid email required"}, 400
    if len(password) < 6:
        return {"error": "Password must be at least 6 characters"}, 400

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            return {"error": "Email already registered"}

        user = User(
            email=email,
            password_hash=hash_password(password),
            subscription_tier="free",
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        token = create_token(user.id, user.email)
        return {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "subscription_tier": user.subscription_tier,
                "subscription_expires_at": None,
            },
        }
    finally:
        db.close()


@router.post("/auth/login")
async def login(body: dict):
    """Login with email + password, returns JWT."""
    email = (body.get("email") or "").strip().lower()
    password = body.get("password", "")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user or not verify_password(password, user.password_hash):
            return {"error": "Invalid email or password"}

        # Check if subscription is still active
        tier = user.subscription_tier
        if tier != "free" and user.subscription_expires_at:
            if user.subscription_expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
                tier = "free"
                user.subscription_tier = "free"
                db.commit()

        token = create_token(user.id, user.email)
        return {
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "subscription_tier": tier,
                "subscription_expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
            },
        }
    finally:
        db.close()


@router.get("/auth/me")
async def get_me(request: Request):
    """Get current user profile from JWT."""
    payload = get_current_user(request)
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == payload["user_id"]).first()
        if not user:
            return {"error": "User not found"}

        tier = user.subscription_tier
        if tier != "free" and user.subscription_expires_at:
            if user.subscription_expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
                tier = "free"
                user.subscription_tier = "free"
                db.commit()

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "subscription_tier": tier,
                "subscription_expires_at": user.subscription_expires_at.isoformat() if user.subscription_expires_at else None,
            },
        }
    finally:
        db.close()


@router.get("/auth/pricing")
async def get_pricing():
    """Return subscription pricing info."""
    return {
        "plans": [
            {"key": "daily", "name": "Day Pass", "price": 9.99, "interval": "day", "label": "Try it out"},
            {"key": "weekly", "name": "Weekly", "price": 49.99, "interval": "week", "label": "Most Popular", "popular": True},
            {"key": "monthly", "name": "Monthly", "price": 98.99, "interval": "month", "label": "Best Value"},
        ],
    }


# ---------------------------------------------------------------------------
# In-memory snapshot cache for instant first load
# ---------------------------------------------------------------------------
_snapshot_cache: dict[str, Any] = {}
_snapshot_ts: float = 0

# ---------------------------------------------------------------------------
# WebSocket broadcast infrastructure
# ---------------------------------------------------------------------------
_ws_clients: set[WebSocket] = set()


async def broadcast(event: dict[str, Any]) -> None:
    """
    Push a JSON event to every connected WebSocket client.

    Other modules (e.g. scheduler jobs) can import and call this to stream
    new arb / discrepancy events to the frontend in real time.

    Args:
        event: Arbitrary dict that will be serialised as JSON.
    """
    if not _ws_clients:
        return

    payload = json.dumps(event, default=str)
    stale: list[WebSocket] = []

    for ws in _ws_clients.copy():
        try:
            await ws.send_text(payload)
        except Exception:
            stale.append(ws)

    for ws in stale:
        _ws_clients.discard(ws)


# ---------------------------------------------------------------------------
# Helper: serialise SQLAlchemy rows to dicts
# ---------------------------------------------------------------------------
def _row_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a SQLAlchemy model instance to a plain dict."""
    d: dict[str, Any] = {}
    for col in obj.__table__.columns:
        attr_name = col.key
        try:
            val = getattr(obj, attr_name, None)
            if hasattr(val, 'tables'):
                continue
            if isinstance(val, datetime):
                val = val.isoformat()
            d[col.name] = val
        except Exception:
            continue

    # ArbOpportunity: legs field may contain full arb/value_bet dict (v3 format)
    # Flatten it so frontend gets all fields at the top level
    legs_data = d.get("legs")
    if isinstance(legs_data, dict) and "event_name" in legs_data:
        full = legs_data
        d["legs"] = full.get("legs", [])
        d["net_profit_pct"] = full.get("net_profit_pct", 0)
        d["net_profit_on_1000"] = full.get("net_profit_on_1000", 0)
        d["arb_type"] = full.get("arb_type", "cross_platform")
        d["confidence"] = full.get("confidence", "medium")
        d["freshness_seconds"] = full.get("freshness_seconds", 0)
        d["annualized_roi"] = full.get("annualized_roi")
        d["end_date"] = full.get("end_date", "")
        # Value bet specific fields
        d["platform"] = full.get("platform", "")
        d["platform_price"] = full.get("platform_price")
        d["consensus_price"] = full.get("consensus_price")
        d["edge"] = full.get("edge")
        d["direction"] = full.get("direction", "")
        d["num_sources"] = full.get("num_sources", 0)
        d["sources"] = full.get("sources", [])
        d["fees"] = full.get("fees", {})

    return d


# ---------------------------------------------------------------------------
# Category system
# ---------------------------------------------------------------------------

async def _trigger_fetch_cycle():
    """Fire all ingestion jobs for the active category, then run arb detection."""
    import asyncio
    from scheduler import fetch_polymarket, fetch_kalshi, fetch_predictit, fetch_manifold, fetch_odds, fetch_metaforecast, run_arb  # noqa: E501

    jobs = [fetch_polymarket, fetch_kalshi, fetch_predictit, fetch_manifold, fetch_metaforecast, fetch_odds]
    for job in jobs:
        try:
            await job()
        except Exception as exc:
            logger.error(f"_trigger_fetch_cycle: {job.__name__} failed: {exc}")
        await asyncio.sleep(1)  # Small delay between jobs to avoid memory spikes

    # Run arb detection on the freshly fetched data
    try:
        await run_arb()
    except Exception as exc:
        logger.error(f"_trigger_fetch_cycle: run_arb failed: {exc}")


@router.get("/categories")
async def get_categories():
    """Return available categories with display info."""
    return {
        "categories": [
            {"key": k, **v}
            for k, v in constants.CATEGORY_DISPLAY.items()
        ],
        "active_category": constants.ACTIVE_CATEGORY,
    }


@router.get("/category")
async def get_category():
    """Return the currently active category."""
    return {"active_category": constants.ACTIVE_CATEGORY}


@router.post("/category")
async def set_category(body: dict):
    """Set the active category. Pass {"category": "politics"} or {"category": null} to clear."""
    import asyncio

    category = body.get("category")
    if category and category not in constants.CATEGORIES:
        return {"error": f"Invalid category. Valid: {constants.CATEGORIES}"}

    # 1. Set the active category
    constants.ACTIVE_CATEGORY = category

    # 2. Deactivate all existing prices and arbs (clean slate for new category)
    db = SessionLocal()
    try:
        db.query(MarketPrice).filter(MarketPrice.is_active == True).update({"is_active": False})  # noqa: E712
        db.query(ArbOpportunity).filter(ArbOpportunity.is_active == True).update({"is_active": False})  # noqa: E712
        db.commit()
    finally:
        db.close()

    # 3. Clear the snapshot cache
    global _snapshot_cache, _snapshot_ts
    _snapshot_cache = {}
    _snapshot_ts = 0

    # 4. Trigger immediate fetch cycle in the background
    if category:
        asyncio.create_task(_trigger_fetch_cycle())

    return {"active_category": category, "status": "ok"}


# ---------------------------------------------------------------------------
# GET /snapshot — ultra-fast cached endpoint for instant first load
# ---------------------------------------------------------------------------
@router.get("/snapshot")
async def get_snapshot():
    """
    Return a cached snapshot of key dashboard data.
    Updates at most once every 30 seconds. Designed to respond instantly
    so the frontend shows something useful before full data loads.
    """
    import time
    global _snapshot_cache, _snapshot_ts

    now = time.time()
    if _snapshot_cache and (now - _snapshot_ts) < 30:
        return _snapshot_cache

    db = SessionLocal()
    try:
        arbs = (
            db.query(ArbOpportunity)
            .filter(ArbOpportunity.is_active == True)  # noqa: E712
            .order_by(ArbOpportunity.profit_pct.desc())
            .limit(10)
            .all()
        )
        discs = (
            db.query(Discrepancy)
            .filter(Discrepancy.is_active == True)  # noqa: E712
            .order_by(Discrepancy.edge_pct.desc())
            .limit(10)
            .all()
        )
        total_markets = db.query(func.count(TrackedMarket.id)).scalar() or 0
        active_arbs = (
            db.query(func.count(ArbOpportunity.id))
            .filter(ArbOpportunity.is_active == True)  # noqa: E712
            .scalar() or 0
        )
        active_discs = (
            db.query(func.count(Discrepancy.id))
            .filter(Discrepancy.is_active == True)  # noqa: E712
            .scalar() or 0
        )

        _snapshot_cache = {
            "arb": [_row_to_dict(a) for a in arbs],
            "discrepancies": [_row_to_dict(d) for d in discs],
            "stats": {
                "total_markets": total_markets,
                "active_arbs": active_arbs,
                "active_discrepancies": active_discs,
            },
            "cached": True,
        }
        _snapshot_ts = now
        return _snapshot_cache
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /opportunities
# ---------------------------------------------------------------------------
@router.get("/debug/prices")
async def debug_prices():
    """Debug: show sample cross-source price data for arb analysis."""
    db = SessionLocal()
    try:
        from sqlalchemy import func, distinct
        # Count prices by source
        source_counts = (
            db.query(MarketPrice.source, func.count(MarketPrice.id))
            .filter(MarketPrice.is_active == True)  # noqa: E712
            .group_by(MarketPrice.source)
            .all()
        )
        # Find events that exist on multiple sources (arb candidates)
        multi = (
            db.query(MarketPrice.event_name, func.count(distinct(MarketPrice.source)))
            .filter(MarketPrice.is_active == True)  # noqa: E712
            .group_by(MarketPrice.event_name)
            .having(func.count(distinct(MarketPrice.source)) >= 2)
            .limit(10)
            .all()
        )
        # For the first multi-source event, show all prices
        sample = []
        if multi:
            event_name = multi[0][0]
            rows = (
                db.query(MarketPrice)
                .filter(MarketPrice.event_name == event_name, MarketPrice.is_active == True)  # noqa: E712
                .all()
            )
            for r in rows[:20]:
                sample.append({
                    "source": r.source, "event": r.event_name[:60], "outcome": r.outcome,
                    "implied_prob": r.implied_probability, "raw_odds": r.raw_odds,
                })
        # Also check ALL prices (not just active)
        all_source_counts = (
            db.query(MarketPrice.source, func.count(MarketPrice.id))
            .group_by(MarketPrice.source)
            .all()
        )
        # Sample some odds_api-adjacent sources
        bookmaker_sample = (
            db.query(MarketPrice.source, MarketPrice.event_name, MarketPrice.outcome, MarketPrice.raw_odds)
            .filter(MarketPrice.source.notin_(["fred", "kalshi", "polymarket", "predictit", "coingecko"]))
            .limit(10)
            .all()
        )
        return {
            "active_source_counts": {s: c for s, c in source_counts},
            "all_source_counts": {s: c for s, c in all_source_counts},
            "multi_source_events": [(e, c) for e, c in multi],
            "sample_prices": sample,
            "bookmaker_sample": [{"source": s, "event": e[:50], "outcome": o, "odds": od} for s, e, o, od in bookmaker_sample],
            "total_active_prices": sum(c for _, c in source_counts),
        }
    finally:
        db.close()


@router.get("/opportunities")
async def get_opportunities(request: Request, limit: int = Query(50, ge=1, le=200)):
    """
    Return active arbitrage opportunities and discrepancies.
    Free users get limited data (first 2 arbs, no discrepancies).
    Premium users get everything.
    """
    # Check auth — allow unauthenticated with limited data
    user_data = get_optional_user(request)
    is_premium = False
    if user_data:
        db_check = SessionLocal()
        try:
            user = db_check.query(User).filter(User.id == user_data["user_id"]).first()
            if user and user.subscription_tier != "free":
                if user.subscription_expires_at and user.subscription_expires_at >= datetime.now(timezone.utc).replace(tzinfo=None):
                    is_premium = True
        finally:
            db_check.close()

    db = SessionLocal()
    try:
        arbs = (
            db.query(ArbOpportunity)
            .filter(ArbOpportunity.is_active == True)  # noqa: E712
            .order_by(ArbOpportunity.profit_pct.desc())
            .limit(limit)
            .all()
        )

        all_arbs = [_row_to_dict(a) for a in arbs]

        if is_premium:
            discs = (
                db.query(Discrepancy)
                .filter(Discrepancy.is_active == True)  # noqa: E712
                .order_by(Discrepancy.edge_pct.desc())
                .limit(limit)
                .all()
            )
            return {
                "arb": all_arbs,
                "discrepancies": [_row_to_dict(d) for d in discs],
                "premium": True,
            }
        else:
            # Free tier: show first 2 arbs, blur the rest
            visible = all_arbs[:2]
            blurred_count = max(0, len(all_arbs) - 2)
            return {
                "arb": visible,
                "discrepancies": [],
                "premium": False,
                "blurred_count": blurred_count,
                "total_count": len(all_arbs),
            }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /markets
# ---------------------------------------------------------------------------
@router.get("/markets")
async def get_markets(limit: int = Query(50, ge=1, le=200)):
    """Return every TrackedMarket with its current status."""
    db = SessionLocal()
    try:
        markets = (
            db.query(TrackedMarket)
            .order_by(TrackedMarket.first_seen.desc())
            .limit(limit)
            .all()
        )
        return {"markets": [_row_to_dict(m) for m in markets]}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /markets/unmapped
# ---------------------------------------------------------------------------
@router.get("/markets/unmapped")
async def get_unmapped_markets():
    """Return tracked markets that have not yet been mapped to a public data source."""
    db = SessionLocal()
    try:
        markets = (
            db.query(TrackedMarket)
            .filter(TrackedMarket.is_mapped == False)  # noqa: E712
            .order_by(TrackedMarket.first_seen.desc())
            .all()
        )
        return {"markets": [_row_to_dict(m) for m in markets]}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------
@router.get("/health")
async def get_health():
    """Return per-source / per-component health status from SystemStatus."""
    db = SessionLocal()
    try:
        rows = db.query(SystemStatus).order_by(SystemStatus.source).all()
        return {"components": [_row_to_dict(r) for r in rows]}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /stats
# ---------------------------------------------------------------------------
@router.get("/stats")
async def get_stats():
    """
    Aggregate dashboard counters.

    Returns:
        total_markets:        number of tracked markets
        active_arbs:          arb opportunities currently active
        active_discrepancies: discrepancies currently active
        alerts_today:         alerts dispatched since midnight UTC
    """
    db = SessionLocal()
    try:
        total_markets = db.query(func.count(TrackedMarket.id)).scalar() or 0

        active_arbs = (
            db.query(func.count(ArbOpportunity.id))
            .filter(ArbOpportunity.is_active == True)  # noqa: E712
            .scalar()
            or 0
        )

        active_discrepancies = (
            db.query(func.count(Discrepancy.id))
            .filter(Discrepancy.is_active == True)  # noqa: E712
            .scalar()
            or 0
        )

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        alerts_today = (
            db.query(func.count(AlertLog.id))
            .filter(AlertLog.sent_at >= today_start)
            .scalar()
            or 0
        )

        # Category breakdown
        category_rows = (
            db.query(TrackedMarket.category, func.count(TrackedMarket.id))
            .filter(TrackedMarket.is_active == True)  # noqa: E712
            .group_by(TrackedMarket.category)
            .all()
        )
        category_breakdown = {cat: cnt for cat, cnt in category_rows if cat}

        # Unmapped markets count
        unmapped_markets = (
            db.query(func.count(TrackedMarket.id))
            .filter(
                TrackedMarket.is_mapped == False,  # noqa: E712
                TrackedMarket.is_active == True,  # noqa: E712
            )
            .scalar()
            or 0
        )

        # Platform status from SystemStatus
        status_rows = db.query(SystemStatus).all()
        platforms = [
            {
                "name": s.source,
                "status": s.status or "unknown",
                "last_success": s.last_success_at.isoformat() if s.last_success_at else None,
                "last_error": s.last_error,
            }
            for s in status_rows
        ]

        # Active discrepancy details for the feed
        disc_rows = (
            db.query(Discrepancy)
            .filter(Discrepancy.is_active == True)  # noqa: E712
            .order_by(Discrepancy.edge_pct.desc())
            .limit(50)
            .all()
        )
        discrepancy_details = [_row_to_dict(d) for d in disc_rows]

        return {
            "total_markets": total_markets,
            "active_arbs": active_arbs,
            "active_discrepancies": active_discrepancies,
            "alerts_today": alerts_today,
            "category_breakdown": category_breakdown,
            "unmapped_markets": unmapped_markets,
            "platforms": platforms,
            "platform_count": len(platforms),
            "discrepancy_details": discrepancy_details,
        }
    finally:
        db.close()


# ---------------------------------------------------------------------------
# POST /alerts/test
# ---------------------------------------------------------------------------
@router.post("/alerts/test")
async def test_alert():
    """
    Fire a test Telegram alert with sample data so the user can verify
    their bot token and chat ID are configured correctly.
    """
    sample_data = {
        "type": "arb",
        "event_name": "Test Arb Opportunity (ignore this alert)",
        "category": "sports",
        "profit_pct": 0.03,
        "legs": [
            {"source": "kalshi", "outcome": "Team A", "odds": 2.40, "stake": 416.67},
            {"source": "polymarket", "outcome": "Team B", "odds": 2.10, "stake": 583.33},
        ],
        "total_stake_base": 1000.0,
        "profit_on_base": 30.0,
        "strategy": "Buy YES on Kalshi @ 0.42, sell YES on Polymarket @ 0.55",
    }

    try:
        from alerts.telegram import send_arb_alert

        await send_arb_alert(sample_data)
        return {"status": "sent", "detail": "Test alert dispatched to Telegram."}
    except ImportError:
        logger.warning("alerts.telegram module not available — skipping test alert")
        return {
            "status": "skipped",
            "detail": "Telegram alert module not yet implemented.",
        }
    except Exception as exc:
        logger.error(f"Test alert failed: {exc}")
        return {"status": "error", "detail": str(exc)}


# ---------------------------------------------------------------------------
# WebSocket /ws/live
# ---------------------------------------------------------------------------
@router.websocket("/ws/live")
async def websocket_live(ws: WebSocket):
    """
    Accept a WebSocket connection and stream JSON events.

    The connection is kept alive until the client disconnects.  Other parts
    of the system push events via the module-level ``broadcast()`` function.
    """
    await ws.accept()
    _ws_clients.add(ws)
    logger.info(f"WebSocket client connected — {len(_ws_clients)} active")

    try:
        # Send a welcome event so the client knows the connection is live
        await ws.send_text(
            json.dumps({"type": "connected", "message": "ArbitrageIQ live feed"})
        )

        # Keep the connection open — wait for client messages (pings / closes)
        while True:
            # We don't expect meaningful inbound messages, but we must
            # await something to detect disconnects.
            data = await ws.receive_text()
            # Echo pings back as pongs
            if data == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as exc:
        logger.debug(f"WebSocket error: {exc}")
    finally:
        _ws_clients.discard(ws)
        logger.info(f"WebSocket clients remaining: {len(_ws_clients)}")
