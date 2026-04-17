"""
ArbitrageIQ — FastAPI application entry point.

Start with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

Lifespan events handle DB init, Telegram bot init, and scheduler start/stop.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from db.models import init_db
from api.routes import router as api_router
from scheduler import start_scheduler, stop_scheduler

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (startup + shutdown)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
      1. Initialise the database (create tables if needed).
      2. Initialise the Telegram bot (if configured).
      3. Start the APScheduler background jobs.
    Shutdown:
      1. Stop the scheduler cleanly.
    """
    # --- Startup ---
    logger.info("ArbitrageIQ starting up ...")

    # 1. Database
    init_db()
    logger.info("Database initialised")

    # 1b. Purge data from removed platforms + cleanup stale data
    try:
        from db.models import cleanup_old_data, SessionLocal, MarketPrice, ArbOpportunity, TrackedMarket
        db = SessionLocal()
        try:
            # Deactivate all prices from platforms we no longer support
            REMOVED_PLATFORMS = ["predictit", "betfair", "smarkets", "matchbook", "manifold"]
            purged_prices = (
                db.query(MarketPrice)
                .filter(MarketPrice.source.in_(REMOVED_PLATFORMS))
                .update({"is_active": False}, synchronize_session=False)
            )
            purged_markets = (
                db.query(TrackedMarket)
                .filter(TrackedMarket.source.in_(REMOVED_PLATFORMS))
                .update({"is_active": False}, synchronize_session=False)
            )
            # Deactivate all arbs (fresh ones will be created on next detection cycle)
            purged_arbs = (
                db.query(ArbOpportunity)
                .filter(ArbOpportunity.is_active == True)  # noqa: E712
                .update({"is_active": False}, synchronize_session=False)
            )
            db.commit()
            logger.info(f"Startup purge: deactivated {purged_prices} prices, {purged_markets} markets, {purged_arbs} arbs from removed platforms")
        finally:
            db.close()
        result = cleanup_old_data(max_age_hours=6, max_per_source=500)
        logger.info(f"Startup cleanup: {result}")
    except Exception as exc:
        logger.warning(f"Startup cleanup failed (non-fatal): {exc}")

    # 2. Telegram alerts disabled (focus on core arb detection)
    logger.info("Telegram alerts disabled")

    # 3. Scheduler
    start_scheduler()
    logger.info("Scheduler started")

    yield  # app is running

    # --- Shutdown ---
    logger.info("ArbitrageIQ shutting down ...")
    stop_scheduler()
    logger.info("Shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(
    title="ArbitrageIQ",
    description="Real-time arbitrage & discrepancy detection across prediction markets",
    version="0.1.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
_frontend_url = os.getenv("FRONTEND_URL", "")
_allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://arbitrageiq-frontend.onrender.com",
]
if _frontend_url and _frontend_url not in _allowed_origins:
    _allowed_origins.append(_frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Rate limiting (simple in-memory, per IP, 60 req/min)
# ---------------------------------------------------------------------------
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT_MAX = 60
_RATE_LIMIT_WINDOW = 60  # seconds


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    # Prune old entries outside the window
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if t > now - _RATE_LIMIT_WINDOW
    ]
    if len(_rate_limit_store[client_ip]) >= _RATE_LIMIT_MAX:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Limit: 60 per minute."},
        )
    _rate_limit_store[client_ip].append(now)
    return await call_next(request)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

# Mount API router — all endpoints defined in api/routes.py are prefixed /api
app.include_router(api_router, prefix="/api")

# Also mount WS at root level so /ws/live works without /api prefix
from api.routes import websocket_live as _ws_live

@app.websocket("/ws/live")
async def ws_root(ws):
    """Root-level WebSocket alias for frontend convenience."""
    await _ws_live(ws)


@app.get("/ping")
async def ping():
    """
    Lightweight health-check endpoint used by the keepalive job
    and external monitoring.
    """
    return {"status": "ok", "service": "arbitrageiq"}
