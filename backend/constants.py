"""
Central configuration for ArbitrageIQ.
All tuneable values live here — nothing hardcoded in logic files.
"""

import os
from dotenv import load_dotenv
# Try Render secret file path first, then local .env
load_dotenv('/etc/secrets/.env')
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# API Keys
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "21143bf79e458a64a2c2f246bb2133fa")

# URLs
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_WS_BASE = "wss://api.elections.kalshi.com/trade-api/v2/ws/v2"
POLYMARKET_API_URL = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")
# Rate limiting — tuned for 512 MB Render Starter plan
BUDGET_MODE = os.getenv("BUDGET_MODE", "true").lower() == "true"
ODDS_API_POLL_SECONDS = 3600 if BUDGET_MODE else 30  # 1 hour — 5-day key rotation budget
KALSHI_POLL_SECONDS = 120
POLYMARKET_POLL_SECONDS = 120
KEEPALIVE_SECONDS = 540

# DB cleanup — keep only this many recent rows per source to cap memory
MAX_PRICES_PER_SOURCE = 1000
PRICE_MAX_AGE_HOURS = 6

MIN_ARB_PROFIT_PCT = 0.001  # 0.1% — real cross-bookmaker arbs are small

# ---------------------------------------------------------------------------
# Platform fee structures — used to compute NET profit after fees
# ---------------------------------------------------------------------------
PLATFORM_FEES = {
    "polymarket": {
        "trade_fee": 0.00,       # 0% maker fee on CLOB
        "withdrawal_fee": 0.00,  # USDC on Polygon, no withdrawal fee
        "profit_fee": 0.00,
    },
    "kalshi": {
        "trade_fee": 0.02,       # ~2% effective spread cost
        "withdrawal_fee": 0.00,
        "profit_fee": 0.00,
    },
    "manifold": {
        "trade_fee": 0.00,
        "withdrawal_fee": 0.00,
        "profit_fee": 0.00,
        "is_play_money": True,   # Mana, not real USD
    },
    "sxbet": {
        "trade_fee": 0.00,
        "withdrawal_fee": 0.00,
        "profit_fee": 0.02,      # 2% commission
    },
    "opinion": {
        "trade_fee": 0.00,       # 0% maker fee
        "withdrawal_fee": 0.00,
        "profit_fee": 0.00,
    },
    "cloudbet": {
        "trade_fee": 0.01,       # ~1% spread
        "withdrawal_fee": 0.00,
        "profit_fee": 0.00,
    },
    "futuur": {
        "trade_fee": 0.00,
        "withdrawal_fee": 0.00,
        "profit_fee": 0.05,      # ~5% on winnings
    },
    "insight": {
        "trade_fee": 0.00,
        "withdrawal_fee": 0.00,
        "profit_fee": 0.00,
    },
    "azuro": {
        "trade_fee": 0.00,       # protocol fees baked into odds
        "withdrawal_fee": 0.00,
        "profit_fee": 0.00,
    },
    "limitless": {
        "trade_fee": 0.00,
        "withdrawal_fee": 0.00,
        "profit_fee": 0.02,      # ~2% protocol fee
    },
    "drift": {
        "trade_fee": 0.001,      # 0.1% taker fee
        "withdrawal_fee": 0.00,
        "profit_fee": 0.00,
    },
}

# ---------------------------------------------------------------------------
# Source classification — determines what counts as a real betting platform
# vs. reference-only forecasting sources (no real money trading)
# ---------------------------------------------------------------------------
TRADEABLE_SOURCES = frozenset({
    "polymarket", "kalshi", "sxbet", "cloudbet", "opinion",
    "futuur", "insight", "azuro", "limitless", "drift",
    # Odds API sportsbooks
    "draftkings", "fanduel", "betmgm", "caesars", "pointsbet",
    "betrivers", "bovada", "bet365", "pinnacle",
    # Odds API aggregators
    "odds_api", "odds_api_io",
})

# Reference-only: useful for consensus/value signals, NOT for placing bets
REFERENCE_SOURCES = frozenset({
    "manifold",  # play money (Mana tokens, not real USD)
    "metaculus", "gjopen", "infer", "foretold", "hypermind",
    "fantasyscotus", "givewellopenphil", "rootclaim",
    "metaculus_mf", "gjopen_mf", "infer_mf", "fantasyscotus_mf",
    "givewellopenphil_mf", "foretold_mf", "hypermind_mf",
})

def is_tradeable_source(source: str) -> bool:
    """Check if a source is a real-money tradeable platform."""
    src = source.lower().strip()
    if src in TRADEABLE_SOURCES:
        return True
    for t in TRADEABLE_SOURCES:
        if t in src:
            return True
    return False

# ---------------------------------------------------------------------------
# Category system — user selects one category at a time to save memory
# ---------------------------------------------------------------------------
CATEGORIES = ["politics", "sports", "crypto", "entertainment", "science_tech", "weather", "other"]

CATEGORY_DISPLAY = {
    "politics":     {"name": "Politics",             "description": "Elections, legislation, government, approval ratings"},
    "sports":       {"name": "Sports",               "description": "NFL, NBA, MLB, NHL, soccer, MMA, Olympics"},
    "crypto":       {"name": "Crypto & Finance",     "description": "Bitcoin, Ethereum, stocks, inflation, interest rates, GDP"},
    "entertainment":{"name": "Entertainment",        "description": "Oscars, box office, music, TV, celebrities, pop culture"},
    "science_tech": {"name": "Science & Tech",       "description": "AI, space, biotech, semiconductors, FDA approvals"},
    "weather":      {"name": "Weather & Climate",    "description": "Temperature records, hurricanes, storms, forecasts"},
    "other":        {"name": "Other",                "description": "Everything else — miscellaneous prediction markets"},
}

# Server-side display filter — used by frontend to filter what's shown.
# Backend fetches ALL categories regardless of this setting.
DISPLAY_CATEGORY: str | None = None

# Manifold quality filter — lowered to capture more markets
MANIFOLD_MIN_VOLUME = 100

KEYWORD_MAP = {
    # --- Politics ---
    "election": "politics", "president": "politics", "senate": "politics",
    "house": "politics", "congress": "politics", "governor": "politics",
    "approval rating": "politics", "poll": "politics", "vote": "politics",
    "democrat": "politics", "republican": "politics", "primary": "politics",
    "impeach": "politics", "resign": "politics", "legislation": "politics",
    "supreme court": "politics", "secretary of state": "politics",
    "speaker": "politics", "cabinet": "politics", "veto": "politics",
    "pardon": "politics", "indictment": "politics", "electoral": "politics",
    # --- Sports ---
    "nfl": "sports", "nba": "sports", "mlb": "sports", "nhl": "sports",
    "super bowl": "sports", "world series": "sports", "playoffs": "sports",
    "championship": "sports", "score": "sports", "touchdown": "sports",
    "point spread": "sports", "mma": "sports", "ufc": "sports",
    "soccer": "sports", "premier league": "sports", "world cup": "sports",
    "olympics": "sports", "tennis": "sports", "golf": "sports",
    "formula 1": "sports", "f1": "sports", "boxing": "sports",
    "batting": "sports", "rushing": "sports", "mvp": "sports",
    # --- Crypto & Finance ---
    "bitcoin": "crypto", "btc": "crypto", "ethereum": "crypto", "eth": "crypto",
    "crypto": "crypto", "solana": "crypto", "dogecoin": "crypto",
    "blockchain": "crypto", "defi": "crypto", "nft": "crypto",
    "binance": "crypto", "coinbase": "crypto", "altcoin": "crypto",
    "token": "crypto", "web3": "crypto", "stablecoin": "crypto",
    "cpi": "crypto", "inflation": "crypto", "unemployment": "crypto",
    "fed rate": "crypto", "federal reserve": "crypto", "fomc": "crypto",
    "interest rate": "crypto", "rate hike": "crypto", "rate cut": "crypto",
    "gdp": "crypto", "recession": "crypto", "oil": "crypto",
    "crude": "crypto", "wti": "crypto", "brent": "crypto",
    "s&p": "crypto", "nasdaq": "crypto", "dow": "crypto",
    "mortgage": "crypto", "treasury": "crypto", "yield": "crypto",
    "jobs report": "crypto", "nonfarm": "crypto", "payroll": "crypto",
    "stock market": "crypto", "tariff": "crypto",
    # --- Entertainment ---
    "oscar": "entertainment", "academy award": "entertainment",
    "box office": "entertainment", "movie": "entertainment", "film": "entertainment",
    "grammy": "entertainment", "emmy": "entertainment", "celebrity": "entertainment",
    "hollywood": "entertainment", "tv show": "entertainment", "series": "entertainment",
    "album": "entertainment", "billboard": "entertainment", "streaming": "entertainment",
    "netflix": "entertainment", "disney": "entertainment", "hbo": "entertainment",
    "spotify": "entertainment", "golden globe": "entertainment",
    "bafta": "entertainment", "cannes": "entertainment", "reality": "entertainment",
    "tony award": "entertainment", "concert": "entertainment",
    "record of the year": "entertainment", "best picture": "entertainment",
    # --- Science & Tech ---
    "ai": "science_tech", "artificial intelligence": "science_tech",
    "spacex": "science_tech", "nasa": "science_tech", "mars": "science_tech",
    "moon": "science_tech", "launch": "science_tech", "quantum": "science_tech",
    "semiconductor": "science_tech", "openai": "science_tech",
    "fda": "science_tech", "drug approval": "science_tech",
    "vaccine": "science_tech", "patent": "science_tech",
    "agi": "science_tech", "gpt": "science_tech", "robot": "science_tech",
    "self-driving": "science_tech", "fusion": "science_tech",
    "crispr": "science_tech", "gene": "science_tech",
    # --- Weather ---
    "temperature": "weather", "high temp": "weather", "low temp": "weather",
    "rainfall": "weather", "precipitation": "weather", "snow": "weather",
    "hurricane": "weather", "tornado": "weather", "storm": "weather",
    "weather": "weather", "degrees": "weather", "fahrenheit": "weather",
    "celsius": "weather", "heat": "weather", "frost": "weather",
    "drought": "weather", "flood": "weather", "wildfire": "weather",
}

# ---------------------------------------------------------------------------
# Backwards compat: code that imports ACTIVE_CATEGORY still works
# ---------------------------------------------------------------------------
ACTIVE_CATEGORY = None  # DEPRECATED — use DISPLAY_CATEGORY. Always fetch all.

# ---------------------------------------------------------------------------
# Discrepancy engine thresholds — minimum edge % per category to report
# ---------------------------------------------------------------------------
THRESHOLDS = {
    "weather": 0.15,
    "crypto": 0.15,
    "politics": 0.10,
    "sports": 0.05,
    "entertainment": 0.10,
    "science_tech": 0.10,
    "other": 0.10,
}

# ---------------------------------------------------------------------------
# Alert configuration
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "PENDING")
ALERT_COOLDOWN_SECONDS = int(os.getenv("ALERT_COOLDOWN_SECONDS", "300"))

# ---------------------------------------------------------------------------
# FRED economic data series — used by discrepancy engine
# ---------------------------------------------------------------------------
FRED_SERIES = {
    "SP500": {"label": "S&P 500", "unit": "index"},
    "UNRATE": {"label": "Unemployment Rate", "unit": "percent"},
    "CPIAUCSL": {"label": "CPI", "unit": "index"},
    "FEDFUNDS": {"label": "Federal Funds Rate", "unit": "percent"},
    "GDP": {"label": "GDP", "unit": "billions"},
    "T10YIE": {"label": "10Y Breakeven Inflation", "unit": "percent"},
    "DFF": {"label": "Effective Federal Funds Rate", "unit": "percent"},
}
