"""
Central configuration for ArbitrageIQ.
All tuneable values live here — nothing hardcoded in logic files.
"""

import os
from dotenv import load_dotenv
# Try Render secret file path first, then local .env
load_dotenv('/etc/secrets/.env')
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# API Keys (fallbacks for Render where env vars may not be configured)
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "bdc9181d902b5410bd4cff7066945065")
FRED_API_KEY = os.getenv("FRED_API_KEY", "314ca443ac2c2b529da3bdd3a2c7c91e")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "PENDING")

# URLs
ODDS_API_BASE = "https://api.the-odds-api.com/v4"
KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_WS_BASE = "wss://api.elections.kalshi.com/trade-api/v2/ws/v2"
POLYMARKET_API_URL = os.getenv("POLYMARKET_API_URL", "https://gamma-api.polymarket.com")
PREDICTIT_API_URL = os.getenv("PREDICTIT_API_URL", "https://www.predictit.org/api/marketdata/all/")
MANIFOLD_API_URL = os.getenv("MANIFOLD_API_URL", "https://api.manifold.markets/v0")
OPEN_METEO_URL = os.getenv("OPEN_METEO_URL", "https://api.open-meteo.com/v1/forecast")
OPEN_METEO_HISTORICAL_URL = os.getenv("OPEN_METEO_HISTORICAL_URL", "https://archive-api.open-meteo.com/v1/archive")
NWS_API_URL = os.getenv("NWS_API_URL", "https://api.weather.gov")
FRED_BASE = "https://api.stlouisfed.org/fred"

# Rate limiting — tuned for 512 MB Render Starter plan
BUDGET_MODE = os.getenv("BUDGET_MODE", "true").lower() == "true"
ODDS_API_POLL_SECONDS = 600 if BUDGET_MODE else 30
KALSHI_POLL_SECONDS = 120
POLYMARKET_POLL_SECONDS = 120
PREDICTIT_POLL_SECONDS = 180
MANIFOLD_POLL_SECONDS = 300
WEATHER_POLL_SECONDS = 900
ECONOMIC_POLL_SECONDS = 3600
KEEPALIVE_SECONDS = 540

# DB cleanup — keep only this many recent rows per source to cap memory
MAX_PRICES_PER_SOURCE = 500
PRICE_MAX_AGE_HOURS = 6

# Discrepancy thresholds
THRESHOLD_WEATHER = float(os.getenv("DISCREPANCY_THRESHOLD_WEATHER", "0.15"))
THRESHOLD_ECONOMIC = float(os.getenv("DISCREPANCY_THRESHOLD_ECONOMIC", "0.15"))
THRESHOLD_POLITICAL = float(os.getenv("DISCREPANCY_THRESHOLD_POLITICAL", "0.10"))
THRESHOLD_SPORTS = float(os.getenv("DISCREPANCY_THRESHOLD_SPORTS", "0.05"))

THRESHOLDS = {
    "weather": THRESHOLD_WEATHER,
    "economic": THRESHOLD_ECONOMIC,
    "political": THRESHOLD_POLITICAL,
    "sports": THRESHOLD_SPORTS,
    "other": 0.10,
}

ALERT_COOLDOWN_SECONDS = 300
MIN_ARB_PROFIT_PCT = 0.001  # 0.1% — real cross-bookmaker arbs are small

FRED_SERIES = {
    "CPIAUCSL":    {"label": "CPI Inflation (YoY %)", "unit": "percent"},
    "UNRATE":      {"label": "US Unemployment Rate", "unit": "percent"},
    "FEDFUNDS":    {"label": "Federal Funds Rate", "unit": "percent"},
    "GDP":         {"label": "US GDP Growth", "unit": "billions"},
    "DCOILWTICO":  {"label": "WTI Crude Oil Price", "unit": "dollars"},
    "DEXUSEU":     {"label": "EUR/USD Exchange Rate", "unit": "ratio"},
    "SP500":       {"label": "S&P 500 Index", "unit": "index"},
    "MORTGAGE30US":{"label": "30-Year Mortgage Rate", "unit": "percent"},
    "T10Y2Y":      {"label": "10Y-2Y Treasury Spread", "unit": "percent"},
    "USREC":       {"label": "US Recession Indicator", "unit": "binary"},
}

KEYWORD_MAP = {
    "temperature": "weather", "high temp": "weather", "low temp": "weather",
    "rainfall": "weather", "precipitation": "weather", "snow": "weather",
    "hurricane": "weather", "tornado": "weather", "storm": "weather",
    "weather": "weather", "degrees": "weather", "fahrenheit": "weather",
    "celsius": "weather", "heat": "weather", "frost": "weather",
    "cpi": "economic", "inflation": "economic", "unemployment": "economic",
    "fed rate": "economic", "federal reserve": "economic", "fomc": "economic",
    "interest rate": "economic", "rate hike": "economic", "rate cut": "economic",
    "gdp": "economic", "recession": "economic", "oil": "economic",
    "crude": "economic", "wti": "economic", "brent": "economic",
    "s&p": "economic", "nasdaq": "economic", "dow": "economic",
    "mortgage": "economic", "treasury": "economic", "yield": "economic",
    "jobs report": "economic", "nonfarm": "economic", "payroll": "economic",
    "election": "political", "president": "political", "senate": "political",
    "house": "political", "congress": "political", "governor": "political",
    "approval rating": "political", "poll": "political", "vote": "political",
    "democrat": "political", "republican": "political", "primary": "political",
    "impeach": "political", "resign": "political",
    "nfl": "sports", "nba": "sports", "mlb": "sports", "nhl": "sports",
    "super bowl": "sports", "world series": "sports", "playoffs": "sports",
    "championship": "sports", "win": "sports", "score": "sports",
    "touchdown": "sports", "point spread": "sports",
}
