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
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

    # 2. Telegram bot (optional — may not be configured yet)
    try:
        from alerts.telegram import init_bot

        await init_bot()
        logger.info("Telegram bot initialised")
    except ImportError:
        logger.warning("alerts.telegram module not available — Telegram alerts disabled")
    except Exception as exc:
        logger.error(f"Telegram bot init failed (non-fatal): {exc}")

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
    allow_origin_regex=r"https://.*\.onrender\.com",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
