# ArbitrageIQ

Real-time arbitrage detection and prediction market discrepancy analysis across sportsbooks and prediction markets. ArbitrageIQ continuously monitors odds from The Odds API (DraftKings, FanDuel, etc.), prediction markets (Kalshi, Polymarket, PredictIt), and public data sources (FRED, Open-Meteo, NWS, CoinGecko) to surface guaranteed-profit arbitrage opportunities and markets that appear mispriced relative to available evidence.

The system runs on a budget-friendly stack (SQLite, APScheduler, free-tier APIs) with a React dashboard that streams updates via WebSocket and sends Telegram alerts for high-value opportunities.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                              │
│                                                                  │
│  The Odds API ──┐   Open-Meteo ──┐   FRED ──────┐               │
│  (sportsbooks)  │   (weather)    │   (economic)  │               │
│                 │                │               │   CoinGecko   │
│  Kalshi ────────┤   NWS Alerts ──┤               │   (crypto) ──┤│
│  Polymarket ────┤                │               │              ││
│  PredictIt ─────┘                └───────────────┘──────────────┘│
└──────────────────────────┬───────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  INGESTION   │  (async httpx, APScheduler)
                    │  MODULES     │  Budget-aware polling
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼────┐ ┌────▼─────┐ ┌────▼──────┐
        │ Arb      │ │Discrep.  │ │ Market    │
        │ Engine   │ │ Engine   │ │ Mapper    │
        │(cross-   │ │(data vs  │ │(auto-     │
        │ book)    │ │ market)  │ │ discover) │
        └─────┬────┘ └────┬─────┘ └───────────┘
              │            │
        ┌─────▼────────────▼─────┐
        │     SQLite Database     │
        │  (MarketPrice, Arb,    │
        │   Discrepancy, etc.)   │
        └─────────┬──────────────┘
                  │
         ┌────────┼────────┐
         │        │        │
    ┌────▼───┐ ┌──▼───┐ ┌──▼──────┐
    │FastAPI │ │ WS   │ │Telegram │
    │REST    │ │/live │ │ Bot     │
    │/api/*  │ │      │ │ Alerts  │
    └────┬───┘ └──┬───┘ └─────────┘
         │        │
    ┌────▼────────▼───────┐
    │  React Dashboard     │
    │  (Vite + Tailwind)   │
    └──────────────────────┘
```

## Quick Start (Local Development)

### Prerequisites
- Python 3.10+
- Node.js 18+
- API keys (run setup script below)

### 1. Clone and setup keys
```bash
git clone https://github.com/yourname/arbitrageiq.git
cd arbitrageiq
python setup/get_keys.py
```

### 2. Start backend
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Start frontend (new terminal)
```bash
cd frontend
npm install
npm run dev
```

### 4. Open dashboard
Navigate to http://localhost:5173

## Render Deployment

### 1. Push to GitHub
```bash
git remote add origin https://github.com/yourname/arbitrageiq.git
git push -u origin main
```

### 2. Deploy on Render
1. Go to [render.com](https://render.com) -> New -> Blueprint
2. Connect your GitHub repo
3. Render will detect `render.yaml` and create both services

### 3. Set environment variables in Render dashboard

| Variable | Where | Value |
|----------|-------|-------|
| `ODDS_API_KEY` | Backend | Your Odds API key |
| `FRED_API_KEY` | Backend | Your FRED API key |
| `TELEGRAM_BOT_TOKEN` | Backend | Your bot token |
| `TELEGRAM_CHAT_ID` | Backend | `PENDING` (auto-set via /start) |
| `BUDGET_MODE` | Backend | `true` |
| `VITE_API_URL` | Frontend | `https://arbitrageiq-backend.onrender.com` |
| `RENDER_EXTERNAL_URL` | Backend | `https://arbitrageiq-backend.onrender.com` |
| `FRONTEND_URL` | Backend | `https://arbitrageiq-frontend.onrender.com` |

## Telegram Registration

After the backend starts:
1. Open Telegram and search for your bot (the one created with BotFather)
2. Send `/start` to register for alerts
3. Send `/test` to verify with a sample alert
4. Send `/status` to check system health

The bot auto-captures your `chat_id` on `/start` -- no manual configuration needed.

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ODDS_API_KEY` | Yes | - | The Odds API key (free tier: 500 req/month) |
| `FRED_API_KEY` | Yes | - | FRED API key for economic data |
| `TELEGRAM_BOT_TOKEN` | No | - | Telegram bot token for alerts |
| `TELEGRAM_CHAT_ID` | No | `PENDING` | Auto-set when user sends /start |
| `BUDGET_MODE` | No | `true` | Caps Odds API to 1 req/5 min |
| `DISCREPANCY_THRESHOLD_WEATHER` | No | `0.15` | Min edge to flag weather discrepancy |
| `DISCREPANCY_THRESHOLD_ECONOMIC` | No | `0.15` | Min edge for economic markets |
| `DISCREPANCY_THRESHOLD_POLITICAL` | No | `0.10` | Min edge for political markets |
| `DISCREPANCY_THRESHOLD_SPORTS` | No | `0.05` | Min edge for sports markets |

## Adding a New Data Source

1. **Create ingestion module**: Add `backend/src/ingestion/your_source.py` with a class that has an async `fetch()` method returning `list[dict]`
2. **Add to scheduler**: In `backend/scheduler.py`, add a `fetch_your_source()` job function and register it in `start_scheduler()` with an appropriate interval
3. **Update keyword map**: Add relevant keywords to `KEYWORD_MAP` in `constants.py` so the market mapper can auto-discover markets for your source
4. **Map to categories**: If your source provides ground-truth data (like weather forecasts), update `market_mapper.py` to include it as a data source for matching markets
5. **Update system status**: Call `_update_system_status()` patterns to track health in the dashboard

## Threshold Tuning

Discrepancy thresholds control the minimum edge (absolute difference between market probability and data-implied probability) required to surface an alert:

- **Lower threshold** = more alerts, more noise, catches smaller edges
- **Higher threshold** = fewer alerts, higher confidence signals

Recommended starting points:
- Sports (0.05): Sportsbook odds are efficient; even 5% edges are significant
- Political (0.10): Prediction markets can be slow to react to news
- Weather/Economic (0.15): Data models have inherent uncertainty; require larger edge

Adjust via environment variables without code changes.
