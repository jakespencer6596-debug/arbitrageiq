# ArbitrageIQ — Implementation Plan for Paid Product Features

## Current State (April 6, 2026)
- 50 cross-platform arbs detected across 4 exchanges (Polymarket, Kalshi, PredictIt, Smarkets)
- 5 discrepancy signals from forecaster consensus
- 1,103 active prices from 7 data sources
- Auth system with login/signup, admin dashboard, PostgreSQL persistence
- Free tier (2 visible arbs) vs Premium ($9.99/day, $49.99/week, $98.99/month)
- Stripe payment integration prepared (placeholder until keys provided)

## Goal
Make ArbitrageIQ a product people will pay $10-100/month for. Every feature below directly drives conversion from free to paid.

---

## Feature 1: Telegram & Discord Alerts

### Why This Matters
This is the #1 reason users pay for OddsJam and OddsShopper. Arbs disappear fast — users need instant push notifications, not manual refreshing. A user who gets a Telegram ping "7.2% arb: Polymarket vs Smarkets — Gavin Newsom" and can act in 30 seconds will pay for the tool.

### Backend

**`backend/src/alerts/alert_service.py`** (new file):
- `send_telegram_alert(user, arb)` — format arb as a clean Telegram message with:
  - Event name, profit %, platforms, direct links
  - Stake amounts for $1K bankroll
  - "Tap to open" deep links to both platforms
- `send_discord_webhook(webhook_url, arb)` — post to user's Discord channel
- Alert deduplication: don't send the same arb to the same user within 10 minutes
- Configurable thresholds: user sets minimum profit % to get alerted (default 2%)

**`backend/src/db/models.py`**:
- Add to User model:
  - `telegram_chat_id` (string, nullable) — user's Telegram chat ID
  - `discord_webhook_url` (string, nullable) — user's Discord webhook
  - `alert_min_profit` (float, default 0.02) — minimum profit % to trigger alert
  - `alerts_enabled` (boolean, default True)

**`backend/src/alerts/telegram_bot.py`** (reactivate existing):
- `/start` command: captures chat_id, links to user account
- `/link EMAIL` command: associates Telegram account with ArbitrageIQ account
- `/settings` command: show/change alert threshold
- `/stop` command: disable alerts

**`backend/scheduler.py`** — modify `run_arb()`:
- After detecting arbs, loop through premium users with alerts enabled
- For each arb exceeding user's threshold, send alert
- Rate limit: max 10 alerts per user per hour

### Frontend

**`frontend/src/components/AlertSettings.jsx`** (new file):
- Settings panel accessible from user menu
- Toggle alerts on/off
- Set minimum profit % slider (1% to 15%)
- Telegram setup instructions with /link command
- Discord webhook URL input
- Test alert button

**`frontend/src/components/Dashboard.jsx`**:
- Add "Alerts" icon in nav bar with badge count
- Link to AlertSettings

### Environment Variables
- `TELEGRAM_BOT_TOKEN` — from BotFather (user creates bot)
- No Discord env vars needed — webhook URL is per-user

### Files to Create
- `backend/src/alerts/alert_service.py`
- `frontend/src/components/AlertSettings.jsx`

### Files to Modify
- `backend/src/db/models.py` — add alert fields to User
- `backend/scheduler.py` — add alert dispatch after arb detection
- `backend/src/alerts/telegram.py` — reactivate with /link command
- `frontend/src/App.jsx` — add AlertSettings route
- `frontend/src/components/Dashboard.jsx` — add alerts nav icon

### Testing
- Register Telegram bot, send /start, verify chat_id captured
- Set alert threshold to 1%, verify arbs above 1% trigger Telegram message
- Verify rate limiting (max 10/hour)
- Test Discord webhook with sample arb payload
- Verify free users cannot access alert settings

---

## Feature 2: Historical Arb Tracking & Analytics

### Why This Matters
Users want proof the tool works before paying. "This arb appeared 12 times this week, average duration 8 minutes, 94% execution success rate" is incredibly compelling. It also helps traders identify patterns — which platform pairs produce the most arbs, which time of day, which categories.

### Backend

**`backend/src/db/models.py`** — new table `ArbHistory`:
```
ArbHistory:
  id (int, PK)
  event_name (string)
  category (string)
  arb_type (string)
  profit_pct (float)
  net_profit_pct (float)
  source_a (string) — first platform
  source_b (string) — second platform
  first_detected_at (datetime)
  last_seen_at (datetime)
  times_detected (int) — how many detection cycles it appeared in
  duration_seconds (int) — time between first and last detection
  peak_profit_pct (float) — highest profit seen
  legs_json (JSON) — full leg data at peak
  status (string) — active, expired, executed
```

**`backend/scheduler.py`** — modify `run_arb()`:
- Before deactivating old arbs, compare new arbs against existing
- If same arb still exists: increment `times_detected`, update `last_seen_at`
- If arb disappeared: set status to "expired", compute final duration
- Store every unique arb in ArbHistory regardless of whether it's currently active

**`backend/src/api/routes.py`** — new endpoints:
- `GET /api/history` — paginated arb history (premium only)
  - Filters: category, platform pair, min profit, date range
  - Returns: list of historical arbs with duration, frequency, peak profit
- `GET /api/analytics` — aggregate stats (premium only)
  - Total arbs found today/week/month
  - Average profit %, average duration
  - Most profitable platform pairs
  - Category breakdown
  - Time-of-day heatmap data
  - "Win rate" — % of arbs that lasted > 5 minutes (executable)

### Frontend

**`frontend/src/components/HistoryPage.jsx`** (new file):
- Table of historical arbs with columns:
  - Event, Platforms, Peak Profit, Times Seen, Duration, First/Last Detected
- Filters: category, platform, date range, min profit
- Click to expand: show full leg details at peak profit

**`frontend/src/components/AnalyticsPage.jsx`** (new file):
- KPI cards: total arbs (today/week/month), avg profit, avg duration
- Chart: arbs per day over last 30 days (line chart)
- Chart: profit distribution histogram
- Chart: platform pair breakdown (bar chart — which pairs produce most arbs)
- Chart: time-of-day heatmap (when do arbs appear most?)
- Category breakdown pie chart
- "Execution window" stat: % of arbs lasting > 1 min, > 5 min, > 30 min

**`frontend/src/components/Dashboard.jsx`**:
- Add "History" and "Analytics" tabs/links in nav
- Premium-only badges on these tabs

### Charts Library
- Add `recharts` (npm install recharts) — lightweight React charting
- Simple bar/line/pie charts, responsive, works with Tailwind

### Files to Create
- `frontend/src/components/HistoryPage.jsx`
- `frontend/src/components/AnalyticsPage.jsx`

### Files to Modify
- `backend/src/db/models.py` — add ArbHistory table
- `backend/scheduler.py` — arb history tracking logic
- `backend/src/api/routes.py` — /history and /analytics endpoints
- `frontend/src/App.jsx` — add routing for history/analytics pages
- `frontend/src/components/Dashboard.jsx` — add nav links
- `frontend/package.json` — add recharts dependency

### Testing
- Run arb detection multiple cycles, verify ArbHistory populates
- Check that same arb across cycles increments times_detected
- Verify expired arbs get correct duration
- Test /api/analytics returns correct aggregates
- Verify charts render correctly
- Verify free users see blurred/locked analytics

---

## Feature 3: Professional Landing Page

### Why This Matters
Right now, visitors hit a login form with no context. A landing page converts visitors to signups by explaining the value proposition, showing social proof, and making the pricing clear. This is the first thing any potential customer sees.

### Frontend

**`frontend/src/components/LandingPage.jsx`** (new file):

**Section 1 — Hero**:
- Headline: "Cross-Platform Prediction Market Arbitrage"
- Subheadline: "Find guaranteed profit opportunities across Polymarket, Kalshi, Smarkets & more. The only tool that scans 7+ prediction market sources in real-time."
- CTA: "Start Free" button → register
- Hero image: screenshot of the arb table with real data
- Trust badges: "7 Data Sources", "50+ Daily Opportunities", "Real-Time Scanning"

**Section 2 — How It Works**:
- Step 1: "Choose a category" — screenshot of category selector
- Step 2: "We scan 7+ exchanges" — animated platform logos
- Step 3: "Act on opportunities" — screenshot of arb with stake calculator

**Section 3 — Features Grid**:
- Cross-platform arb detection
- Fee-adjusted net profit
- Forecaster consensus intelligence
- Execution step-by-step guides
- Stake calculator with copy-to-clipboard
- Real-time auto-updating
- 7 market categories

**Section 4 — Live Stats** (fetched from API):
- "X arbs active right now"
- "X markets monitored"
- "X data sources scanning"
- Auto-refreshing counters

**Section 5 — Pricing**:
- Three cards (Day $9.99 / Week $49.99 / Month $98.99)
- Feature comparison: Free vs Premium
- "Start Free — No credit card required"

**Section 6 — FAQ**:
- "What is prediction market arbitrage?"
- "Which platforms do you support?"
- "Is this legal?"
- "How fast do arbs disappear?"
- "Can I really make money with this?"

**Section 7 — Footer**:
- Links, social, support email
- "Built for prediction market traders"

### App.jsx Changes
- If not authenticated: show LandingPage instead of LoginPage
- LandingPage has "Login" and "Sign Up" buttons that open LoginPage as a modal

### Files to Create
- `frontend/src/components/LandingPage.jsx`

### Files to Modify
- `frontend/src/App.jsx` — show LandingPage for unauthenticated users
- `backend/src/api/routes.py` — add `GET /api/public/stats` endpoint (no auth, returns live arb count + market count for landing page)

### Assets Needed
- Screenshots of the tool in action (can be captured via MCP)
- Platform logos (Polymarket, Kalshi, Smarkets, etc.)

---

## Feature 4: Mobile Optimization

### Why This Matters
Most traders check opportunities on their phones. The current table-based layout is unusable on mobile. A card-based responsive layout that works on phones is essential for a paid product.

### Frontend Changes

**`frontend/src/components/ArbTable.jsx`**:
- Below `md` breakpoint (< 768px): switch from table to card layout
- Each arb as a card showing:
  - Profit % badge (large, tappable)
  - Event name
  - Platform badges with links
  - Net on $1K
  - Tap to open StakeCalculator
- Swipe gestures: swipe left for quick-action buttons

**`frontend/src/components/ArbCard.jsx`** (new file):
- Mobile-optimized arb display card
- Large tap targets for platform links
- Compact but readable layout
- Confidence dot + stale badge inline

**`frontend/src/components/Dashboard.jsx`**:
- Mobile: stack arb table and discrepancy feed vertically (already done via grid)
- Mobile nav: hamburger menu with category, user menu, alerts
- Bottom nav bar for mobile: Home | Arbs | Signals | History | Settings

**`frontend/src/components/StakeCalculator.jsx`**:
- Full-screen modal on mobile (already mostly works)
- Larger tap targets for copy buttons
- Bankroll quick-select buttons should be larger on mobile

**General responsive fixes**:
- Test all components at 375px width (iPhone SE)
- Ensure no horizontal scrolling
- Font sizes: minimum 14px for body text on mobile
- Touch targets: minimum 44px height

### Files to Create
- `frontend/src/components/ArbCard.jsx`

### Files to Modify
- `frontend/src/components/ArbTable.jsx` — add mobile card view
- `frontend/src/components/Dashboard.jsx` — mobile nav improvements
- `frontend/src/components/StakeCalculator.jsx` — mobile touch improvements
- `frontend/index.html` — add viewport meta tag (should already exist)

### Testing
- Test on Chrome DevTools mobile simulator (iPhone SE, iPhone 14, Pixel 7)
- Verify all tap targets are large enough
- Verify no horizontal scroll
- Test StakeCalculator modal on small screens
- Test category selector on mobile

---

## Feature 5: Bet Tracker & P&L

### Why This Matters
RebelBetting's BetTracker is their most-loved feature. Users want to log their actual bets, track real P&L, and see if the tool is actually making them money. This turns the tool from "interesting data" into "my trading system."

### Backend

**`backend/src/db/models.py`** — new table `BetLog`:
```
BetLog:
  id (int, PK)
  user_id (int, FK to users)
  arb_event_name (string)
  platform (string) — which exchange the bet was placed on
  direction (string) — YES or NO
  odds (float)
  stake (float)
  potential_payout (float)
  status (string) — pending, won, lost, void
  actual_payout (float, nullable) — filled when resolved
  profit_loss (float, nullable) — filled when resolved
  placed_at (datetime)
  resolved_at (datetime, nullable)
  notes (string, nullable)
  arb_id (int, nullable) — link to the arb that generated this bet
```

**`backend/src/api/routes.py`** — new endpoints:
- `POST /api/bets` — log a new bet (premium only)
- `GET /api/bets` — list user's bets with filters (premium only)
- `PUT /api/bets/{id}` — update bet (mark as won/lost, enter actual payout)
- `GET /api/bets/summary` — P&L summary (premium only)
  - Total bets, win rate, total staked, total profit/loss
  - ROI %, profit by platform, profit by category
  - Monthly P&L breakdown

### Frontend

**`frontend/src/components/BetTracker.jsx`** (new file):
- List of logged bets with status (pending/won/lost)
- Quick-log from StakeCalculator: "I placed this bet" button per leg
- Manual entry form: platform, direction, odds, stake, notes
- Inline resolution: "Did you win?" buttons to mark outcome
- Filter by: status, platform, category, date range

**`frontend/src/components/PLSummary.jsx`** (new file):
- KPI cards: Total P&L, Win Rate, ROI, Total Staked
- Monthly P&L chart (bar chart, green/red by month)
- Platform breakdown: which exchange makes you the most money
- Category breakdown: which market type is most profitable

**StakeCalculator integration**:
- After viewing an arb in StakeCalculator, add "Log This Bet" button per leg
- Pre-fills platform, odds, stake from the calculator
- Quick one-tap logging

### Files to Create
- `frontend/src/components/BetTracker.jsx`
- `frontend/src/components/PLSummary.jsx`

### Files to Modify
- `backend/src/db/models.py` — add BetLog table
- `backend/src/api/routes.py` — add bet CRUD endpoints
- `frontend/src/components/StakeCalculator.jsx` — add "Log This Bet" buttons
- `frontend/src/App.jsx` — add routing for bet tracker
- `frontend/src/components/Dashboard.jsx` — add "Bets" tab in nav

### Testing
- Log a bet from StakeCalculator
- Mark bet as won, verify P&L updates
- Check summary stats accuracy
- Verify free users cannot access bet tracker
- Test on mobile

---

## Implementation Order

| Priority | Feature | Effort | Impact on Conversions |
|----------|---------|--------|----------------------|
| 1 | **Landing Page** | 1 day | HIGH — first impression, explains value |
| 2 | **Mobile Optimization** | 1 day | HIGH — 60%+ of users are on mobile |
| 3 | **Telegram/Discord Alerts** | 2 days | VERY HIGH — #1 paid feature in competitor tools |
| 4 | **Historical Tracking + Analytics** | 2-3 days | HIGH — proves the tool works, shows patterns |
| 5 | **Bet Tracker + P&L** | 2-3 days | MEDIUM — retention feature, keeps users engaged |

**Total estimated effort: 8-11 days**

## Revenue Projections

Based on competitor data and TAM analysis:
- Free users → 5-10% convert to paid within 30 days
- Average revenue per paid user: ~$50/month (mix of day/week/month plans)
- Target: 100 paid users in first 3 months = $5,000/month
- Target: 500 paid users in first year = $25,000/month

## Marketing Channels (Post-Build)

1. **Reddit**: r/polymarket, r/predictit, r/sportsbetting, r/arbitragebetting — post case studies showing real arbs found
2. **Twitter/X**: Daily arb opportunity highlights, prediction market commentary
3. **Discord**: Create ArbitrageIQ community, free tier gets access, premium gets alerts channel
4. **YouTube**: "How I found a 7% arb between Polymarket and Smarkets" tutorial videos
5. **Product Hunt**: Launch as "The first cross-platform prediction market arbitrage scanner"
6. **SEO**: Target "prediction market arbitrage", "polymarket vs kalshi", "prediction market tools"

## Technical Debt to Address

1. Fix Smarkets URL generation (currently empty for some arbs)
2. Add Kalshi orderbook depth to existing integration
3. Fix confidence scoring (most arbs show "low" — need better volume data)
4. Add Polymarket CLOB bid/ask to existing integration
5. Monitor SX Bet API stability (currently degraded)
6. Set up proper error monitoring (Sentry or similar)
7. Add rate limiting per user for API endpoints
8. Set up automated backups for PostgreSQL
