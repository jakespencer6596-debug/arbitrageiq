# ArbitrageIQ Improvement Roadmap

## Current State (v1 - April 2026)
- 36 real cross-platform arbs detected (Polymarket vs PredictIt, some Manifold/Kalshi)
- Category-based loading (7 sectors), entity-aware matching
- Deployed on Render free tier (512MB), SQLite
- Politics category works well; other categories have minimal cross-platform overlap

---

## PHASE 1: Fee-Adjusted Profits (Critical Fix)
**Why:** PredictIt charges 10% profit fee + 5% withdrawal fee. A 5% gross arb on PredictIt is actually a NET LOSS. Users will lose money following current profit numbers.

**Changes:**
- Add `PLATFORM_FEES` dict to `constants.py`:
  - Polymarket: ~0% trade, 0% withdrawal
  - Kalshi: ~1-2% effective spread cost
  - PredictIt: 10% profit fee + 5% withdrawal fee
  - Manifold: play money (flag as "paper only")
- Modify `arb_engine.py` to compute `net_profit_after_fees` for each arb
- Display net profit (not gross) in ArbTable, with a tooltip showing fee breakdown
- Filter out arbs where net profit < 0% after fees
- Add fee info to StakeCalculator modal

**Impact:** Prevents users from executing unprofitable trades. Builds trust.

---

## PHASE 2: Add Betfair Exchange (Biggest Source Expansion)
**Why:** Betfair is the world's largest betting exchange with massive liquidity and the sharpest prices. It covers politics, sports, entertainment, and specials. Adding it roughly doubles cross-platform overlap.

**Changes:**
- New file: `backend/src/ingestion/betfair.py`
  - Betfair Exchange API (free developer account, 20 req/sec)
  - Endpoints: `listMarketCatalogue`, `listMarketBook`
  - Covers: politics, sports, entertainment, specials
- Add Betfair keywords to `KEYWORD_MAP`
- Add to scheduler with 60-second polling interval
- Build `_build_market_url` for Betfair (`betfair.com/exchange/plus/...`)

**Limitation:** Betfair is not available to US users directly, but API access from a server works. Note this in the UI.

**Impact:** Dramatically increases arb detection across all categories, especially sports and entertainment.

---

## PHASE 3: Cross-Bookmaker Sports Arbs
**Why:** Currently 0 sports arbs because the engine only handles binary YES/NO. Sports markets are multi-outcome (Team A vs Team B vs Draw). The Odds API already provides bookmaker-level odds but they're not being used for cross-book arbs.

**Changes:**
- New function `detect_sports_arb()` in `arb_engine.py`:
  - Group all outcomes for the same event (using Odds API event_id)
  - For each outcome, find the best odds across all bookmakers
  - Compute N-way arb: `sum(1/best_odds_i) < 1.0`
  - Support 2-way (moneyline), 3-way (soccer), and spread markets
- Modify `run_arb()` in scheduler to call both `detect_arb()` (prediction markets) and `detect_sports_arb()` (sportsbooks) when category is "sports"
- Fix Odds API key (currently 401 - expired)

**Impact:** Unlocks the entire sports betting arbitrage market, which is the most active arb space.

---

## PHASE 4: WebSocket Real-Time Feeds
**Why:** Current 120-second HTTP polling means arbs can appear and disappear between polls. Kalshi and Polymarket both offer WebSocket feeds for sub-second price updates. `KALSHI_WS_BASE` is already in constants but unused.

**Changes:**
- New WebSocket client for Kalshi (`wss://api.elections.kalshi.com/trade-api/v2/ws/v2`)
  - Subscribe to price updates for active category markets
  - Update MarketPrice rows in real-time
- Polymarket CLOB WebSocket for orderbook-level data
  - Also provides liquidity depth information
- Keep HTTP polling as fallback for PredictIt and Manifold (no WS available)
- Trigger arb detection on price update events (not just timer-based)

**Impact:** Detection latency drops from 2 minutes to under 5 seconds. Critical for sports arbs which exist for seconds.

---

## PHASE 5: Liquidity & Execution Data
**Why:** A 5% arb is useless if the market only has $50 of liquidity. Users need to know if they can actually execute.

**Changes:**
- Add `volume` and `liquidity` fields to arb API response
- Polymarket CLOB API: fetch orderbook depth per market
- Kalshi: use `open_interest` and `volume` already being fetched
- PredictIt: use `bestBuyYesCost`/`bestBuyNoCost` spread (already in raw_payload)
- Frontend: Add liquidity badge to ArbTable rows
  - Green: >$10K available
  - Yellow: $1K-$10K
  - Red: <$1K (high execution risk)
- Add execution risk warning in StakeCalculator when stake > available liquidity

**Impact:** Users can assess whether an arb is actually executable before attempting it.

---

## PHASE 6: Better Event Matching
**Why:** Jaccard similarity misses valid matches when platforms phrase events very differently. Also misses matches where one platform uses the specific candidate and another uses the generic market name.

**Changes:**
- Replace Jaccard with `rapidfuzz.fuzz.token_sort_ratio` (handles word reordering, C-optimized)
  - `pip install rapidfuzz` (no heavy dependencies)
  - threshold ~70 (on 0-100 scale) replaces Jaccard 0.55
- Add **resolution date matching**: store market close/resolution dates, require overlap
- Add **confidence score** to each arb (based on matching quality + volume + freshness)
- Consider adding sentence embeddings as a second-pass matcher for higher recall
  - `sentence-transformers/all-MiniLM-L6-v2` (small model, ~80MB)
  - Only viable if we move off 512MB Render free tier

**Impact:** Catches more real arbs while maintaining low false positive rate.

---

## PHASE 7: Annualized ROI & Time Context
**Why:** A 3% arb that locks capital for 6 months is only 6% annualized - worse than a savings account. Users need time context.

**Changes:**
- Add `resolution_date` / `end_date` to MarketPrice model (most APIs provide this)
- Compute annualized ROI: `(1 + profit_pct) ^ (365 / days_to_resolution) - 1`
- Display both raw profit% and annualized ROI in ArbTable
- Add "Time to Resolution" column showing "3 days", "2 months", etc.
- Sort by annualized ROI as an option (short-duration arbs are much more valuable)

**Impact:** Helps users prioritize arbs that offer the best risk-adjusted returns.

---

## PHASE 8: Same-Market Overround Detection
**Why:** PredictIt multi-candidate markets (e.g., "Who will win?") often have all YES contracts summing to >100%. You can sell all contracts for guaranteed profit. This is a completely separate arb strategy that works on a single platform.

**Changes:**
- New function `detect_overround()` in `arb_engine.py`
  - Group all contracts within the same PredictIt/Kalshi market
  - Sum implied probabilities
  - If sum > 1.0 (for selling) or sum < 1.0 (for buying), flag as arb
  - Calculate optimal stake allocation across all contracts
- Works especially well on PredictIt where contract prices are sticky

**Impact:** New class of arbs that doesn't require cross-platform matching at all. Higher reliability.

---

## PHASE 9: Additional Data Sources
**Priority order:**

### Metaculus (Free, Easy)
- Community forecasting platform with well-calibrated predictions
- Not a betting market (no direct arbs), but excellent ground truth for discrepancy engine
- Free API: `https://www.metaculus.com/api2/questions/`
- ~5,000 active questions overlapping with Polymarket/Kalshi

### Smarkets (Free, Good Overlap)
- UK-based betting exchange, lower commissions than Betfair (2% vs 5%)
- Free REST + WebSocket API
- Strong on politics and sports

### Polymarket CLOB API (Already Available)
- You only use the Gamma API (summary prices). The CLOB API provides:
  - Orderbook depth (bid/ask at each price level)
  - Real-time trade stream
  - Better price accuracy than Gamma snapshots

### Pinnacle API (Sharp Odds Reference)
- Pinnacle is considered the sharpest sportsbook
- Free API (requires account)
- Use as a benchmark: if another book's odds differ significantly from Pinnacle, that's a value bet

---

## PHASE 10: UX & Execution Improvements

### Execution Workflow
- Step-by-step guided betting: "Step 1: Open Polymarket link, buy YES at $0.36. Step 2: Open PredictIt link, buy NO at $0.55"
- Copy-to-clipboard for each step (partially implemented in StakeCalculator)
- Show which leg to execute first (the less liquid market first, to check it's still available)

### Stale Price Warnings
- Show "fetched_at" age on each arb
- Dim/flag arbs older than 60 seconds
- Add a "Refresh" button to trigger immediate re-fetch

### Historical Tracking
- Track arb appearances over time: "This arb appeared 5 times today, average duration 4 min"
- Show profitability trends by category
- Track which platform pairs produce the most arbs

### Discord/Webhook Alerts
- Add Discord webhook support alongside Telegram
- Configurable alert thresholds (only alert on >3% net profit)
- Rate limiting per market to avoid spam

### Mobile Optimization
- Category selector already responsive
- Ensure ArbTable is usable on small screens (collapse columns, swipe for details)

---

## Infrastructure Considerations

### Render Tier Upgrade
Most of Phases 4-9 require more than 512MB RAM:
- WebSocket connections consume persistent memory
- Sentence embeddings need ~200MB
- More data sources = more concurrent data in memory
- **Recommendation:** Upgrade to Render Starter ($7/mo, 1GB RAM) or Standard ($25/mo, 2GB RAM)

### Database
- SQLite is fine for current scale
- If adding 5+ sources with real-time WebSocket feeds, consider PostgreSQL (Render offers free 256MB Postgres)
- Postgres enables better concurrent writes and query performance

### Caching Layer
- Add Redis (Render offers free Redis) for:
  - Price deduplication across WebSocket updates
  - Arb result caching (avoid recalculating every cycle)
  - Rate limit tracking per source

---

## Priority Matrix

| Phase | Effort | Impact | Dependencies |
|-------|--------|--------|-------------|
| 1. Fee-Adjusted Profits | Small (1 day) | CRITICAL | None |
| 2. Betfair Exchange | Medium (2-3 days) | Very High | Betfair account |
| 3. Sports Multi-Outcome | Medium (2-3 days) | High | Fix Odds API key |
| 4. WebSocket Feeds | Medium (2-3 days) | High | Phase 2 |
| 5. Liquidity Data | Small (1-2 days) | High | Phase 4 for CLOB |
| 6. Better Matching | Medium (2 days) | Medium | rapidfuzz install |
| 7. Annualized ROI | Small (1 day) | Medium | Resolution dates |
| 8. Overround Detection | Small (1-2 days) | Medium | None |
| 9. More Sources | Large (1 week) | Medium | Betfair first |
| 10. UX Improvements | Medium (3-4 days) | Medium | None |

**Recommended execution order:** Phase 1 -> 8 -> 2 -> 3 -> 5 -> 7 -> 4 -> 6 -> 10 -> 9
