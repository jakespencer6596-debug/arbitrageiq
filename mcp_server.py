"""
ArbitrageIQ MCP Server

Exposes the ArbitrageIQ backend API as Claude Code tools.
Connects to either local (localhost:8000) or production (Render) backend.

Usage:
    python mcp_server.py [--url https://arbitrageiq-backend.onrender.com]
"""

import os
import sys
import json
import httpx
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BACKEND_URL = os.getenv(
    "ARBITRAGEIQ_URL",
    "https://arbitrageiq-backend.onrender.com",
)

mcp = FastMCP("ArbitrageIQ")

# ---------------------------------------------------------------------------
# Shared HTTP client
# ---------------------------------------------------------------------------
def _client() -> httpx.Client:
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def _get(path: str, params: dict | None = None) -> dict:
    """GET helper with error handling."""
    with _client() as c:
        r = c.get(path, params=params)
        r.raise_for_status()
        return r.json()


def _post(path: str, json_body: dict | None = None) -> dict:
    """POST helper with error handling."""
    with _client() as c:
        r = c.post(path, json=json_body)
        r.raise_for_status()
        return r.json()


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def ping() -> str:
    """Check if the ArbitrageIQ backend is alive."""
    data = _get("/ping")
    return json.dumps(data, indent=2)


@mcp.tool()
def get_stats() -> str:
    """
    Get aggregate dashboard stats: total markets, active arbs,
    active discrepancies, alerts today, platform statuses, and category breakdown.
    """
    data = _get("/api/stats")
    return json.dumps(data, indent=2)


@mcp.tool()
def get_opportunities(limit: int = 50) -> str:
    """
    Get active arbitrage opportunities and discrepancies.
    Arbs sorted by profit % descending, discrepancies by edge % descending.
    """
    data = _get("/api/opportunities", {"limit": limit})
    return json.dumps(data, indent=2)


@mcp.tool()
def get_snapshot() -> str:
    """
    Get a fast cached snapshot of key dashboard data (top 10 arbs,
    top 10 discrepancies, basic stats). Refreshes every 30 seconds.
    """
    data = _get("/api/snapshot")
    return json.dumps(data, indent=2)


@mcp.tool()
def get_markets(limit: int = 50) -> str:
    """Get all tracked markets with their current status."""
    data = _get("/api/markets", {"limit": limit})
    return json.dumps(data, indent=2)


@mcp.tool()
def get_unmapped_markets() -> str:
    """Get tracked markets not yet mapped to a public data source."""
    data = _get("/api/markets/unmapped")
    return json.dumps(data, indent=2)


@mcp.tool()
def get_health() -> str:
    """Get per-source / per-component health status (Kalshi, Polymarket, OddsAPI, etc.)."""
    data = _get("/api/health")
    return json.dumps(data, indent=2)


@mcp.tool()
def debug_prices() -> str:
    """
    Debug tool: show cross-source price data for arb analysis.
    Shows source counts, multi-source events, and sample prices.
    """
    data = _get("/api/debug/prices")
    return json.dumps(data, indent=2)


@mcp.tool()
def test_telegram_alert() -> str:
    """Fire a test Telegram alert to verify bot token and chat ID are working."""
    data = _post("/api/alerts/test")
    return json.dumps(data, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Allow overriding URL via CLI arg
    if "--url" in sys.argv:
        idx = sys.argv.index("--url")
        if idx + 1 < len(sys.argv):
            BACKEND_URL = sys.argv[idx + 1]
            print(f"Using backend URL: {BACKEND_URL}", file=sys.stderr)

    # For local dev: --local shortcut
    if "--local" in sys.argv:
        BACKEND_URL = "http://localhost:8000"
        print("Using local backend: http://localhost:8000", file=sys.stderr)

    mcp.run()
