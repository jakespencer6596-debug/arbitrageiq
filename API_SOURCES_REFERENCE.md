# Prediction Market & Betting Exchange API Reference

## Compiled: April 2026
## Purpose: Cross-platform arbitrage data sources for ArbitrageIQ

---

## STATUS LEGEND
- **CONFIRMED WORKING** = Tested via curl, returns valid data
- **REQUIRES AUTH** = API exists but needs API key / token
- **DEAD/UNAVAILABLE** = Endpoint down, certificate expired, or 404
- **SPORTS ONLY** = Working but only covers sports markets (limited arb value for political/crypto)

---

## 1. POLYMARKET GAMMA API (Already Integrated)

| Field | Value |
|-------|-------|
| **Status** | CONFIRMED WORKING |
| **Base URL** | `https://gamma-api.polymarket.com` |
| **Auth** | None required |
| **Free?** | Yes, no rate limit published (tested ~100 req/min OK) |
| **Data** | Prices, outcomes, volume, slug, end_date, events grouping |
| **Markets** | Politics, crypto, entertainment, science, world events |

### Key Endpoints
```
GET /markets?closed=false&limit=100&offset=0
GET /events?closed=false&limit=100&order=volume&ascending=false
GET /events?closed=false&tag=politics
```

### curl Example
```bash
curl "https://gamma-api.polymarket.com/markets?closed=false&limit=2"
```

### Key Response Fields
- `question`, `conditionId`, `slug`, `outcomePrices` (JSON string: `["0.535","0.465"]`)
- `outcomes` (JSON string: `["Yes","No"]`), `volume`, `liquidity`, `enableOrderBook`
- `clobTokenIds` (JSON string with token IDs for CLOB API)
- `volume24hr`, `volume1wk`, `volume1mo`, `bestBid`, `bestAsk`

---

## 2. POLYMARKET CLOB API (NEW - High Priority)

| Field | Value |
|-------|-------|
| **Status** | CONFIRMED WORKING |
| **Base URL** | `https://clob.polymarket.com` |
| **Auth** | None for read-only (API key required for trading) |
| **Free?** | Yes for market data reads |
| **Data** | Full orderbook depth, midpoint, spread, last trade, simplified markets |
| **Markets** | Same as Polymarket Gamma |
| **Rate Limits** | Not published, tested ~30 req/min OK |

### Key Endpoints (All CONFIRMED WORKING)
```
GET /book?token_id={TOKEN_ID}            # Full orderbook (bids + asks)
GET /midpoint?token_id={TOKEN_ID}        # Midpoint price
GET /spread?token_id={TOKEN_ID}          # Bid-ask spread
GET /last-trade-price?token_id={TOKEN_ID} # Last executed trade
GET /sampling-markets                     # Paginated list of all active CLOB markets
GET /simplified-markets                   # Compact market list with token/price data
GET /markets?limit=500                    # All CLOB markets with full metadata
```

### curl Examples
```bash
# Get orderbook depth
curl "https://clob.polymarket.com/book?token_id=8501497159083948713316135768103773293754490207922884688769443031624417212426"

# Get midpoint price
curl "https://clob.polymarket.com/midpoint?token_id=8501497159083948713316135768103773293754490207922884688769443031624417212426"
# Returns: {"mid":"0.535"}

# Get spread
curl "https://clob.polymarket.com/spread?token_id=8501497159083948713316135768103773293754490207922884688769443031624417212426"
# Returns: {"spread":"0.01"}

# Get last trade
curl "https://clob.polymarket.com/last-trade-price?token_id=8501497159083948713316135768103773293754490207922884688769443031624417212426"
# Returns: {"price":"0.54","side":"BUY"}
```

### Orderbook Response Format
```json
{
  "market": "0x...",
  "asset_id": "850149...",
  "bids": [{"price":"0.53","size":"690.57"}, {"price":"0.52","size":"478.14"}, ...],
  "asks": [{"price":"0.54","size":"200"}, {"price":"0.55","size":"1500"}, ...]
}
```

### Integration Note
Token IDs come from the Gamma API `clobTokenIds` field. The workflow is:
1. Gamma API -> get markets with `clobTokenIds`
2. CLOB API -> get orderbook depth for each token_id
This gives you the TRUE executable price, not just indicative midpoints.

---

## 3. KALSHI API (Already Integrated - URL UPDATE NEEDED)

| Field | Value |
|-------|-------|
| **Status** | CONFIRMED WORKING (new URL) |
| **Base URL** | `https://api.elections.kalshi.com/trade-api/v2` |
| **Old URL** | `https://trading-api.kalshi.com/trade-api/v2` (returns redirect warning) |
| **Auth** | None for market data reads |
| **Free?** | Yes for read-only data |
| **Data** | Prices, orderbook, volume, event grouping, bid/ask |
| **Markets** | Politics, world events, crypto, sports, entertainment, science |

### Key Endpoints
```
GET /markets?status=open&limit=100                           # All open markets
GET /markets?status=open&limit=100&cursor={CURSOR}           # Paginated
GET /events?status=open&limit=100&with_nested_markets=true   # Events with grouped markets
GET /markets/{TICKER}/orderbook                              # Full orderbook depth
```

### curl Examples
```bash
# Markets listing
curl "https://api.elections.kalshi.com/trade-api/v2/markets?status=open&limit=2"

# Events with nested markets
curl "https://api.elections.kalshi.com/trade-api/v2/events?status=open&limit=2&with_nested_markets=true"

# Orderbook (CONFIRMED WORKING)
curl "https://api.elections.kalshi.com/trade-api/v2/markets/KXNEWPOPE-70-PPIZ/orderbook"
```

### Orderbook Response Format
```json
{
  "orderbook_fp": {
    "yes_dollars": [["0.04","2006.00"], ["0.03","2000.00"]],
    "no_dollars": [["0.01","490001.00"], ["0.95","15.00"]]
  }
}
```

### Key Response Fields (Markets)
- `ticker`, `event_ticker`, `title`, `status`, `category`
- `yes_ask_dollars`, `yes_bid_dollars`, `no_ask_dollars`, `no_bid_dollars`
- `last_price_dollars`, `volume_fp`, `open_interest_fp`
- `close_time`, `expiration_time`

### CRITICAL: Update constants.py
```python
KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"  # NEW
# OLD: "https://trading-api.kalshi.com/trade-api/v2"  # Returns redirect
```

---

## 4. PREDICTIT API (Already Integrated)

| Field | Value |
|-------|-------|
| **Status** | CONFIRMED WORKING |
| **Base URL** | `https://www.predictit.org/api/marketdata/all/` |
| **Auth** | None |
| **Free?** | Yes, no published limits |
| **Data** | Last trade, best buy/sell yes/no prices per contract |
| **Markets** | US politics primarily |

### curl Example
```bash
curl "https://www.predictit.org/api/marketdata/all/"
```

### Key Response Fields
- `markets[].id`, `name`, `url`
- `contracts[].lastTradePrice`, `bestBuyYesCost`, `bestBuyNoCost`
- `bestSellYesCost`, `bestSellNoCost`, `lastClosePrice`, `status`

---

## 5. MANIFOLD MARKETS API (Already Integrated)

| Field | Value |
|-------|-------|
| **Status** | CONFIRMED WORKING |
| **Base URL** | `https://api.manifold.markets/v0` |
| **Auth** | None for reads |
| **Free?** | Yes |
| **Data** | Probability, volume, pool sizes, resolution status |
| **Markets** | PLAY MONEY (Mana) - politics, crypto, entertainment, everything |
| **Note** | Play money only, but probabilities reflect forecaster consensus |

### Key Endpoints
```
GET /search-markets?term=&sort=liquidity&limit=100&offset=0
GET /market/{SLUG}
GET /market/{ID}
```

---

## 6. METAFORECAST GRAPHQL (Already Integrated)

| Field | Value |
|-------|-------|
| **Status** | CONFIRMED WORKING |
| **Base URL** | `https://metaforecast.org/api/graphql` |
| **Auth** | None |
| **Free?** | Yes |
| **Data** | Aggregated probabilities from 10+ platforms |
| **Platforms** | Metaculus, GJOpen, INFER, Hypermind, Rootclaim, Betfair, PredictIt, Polymarket |

### curl Example
```bash
curl -X POST "https://metaforecast.org/api/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ questions(first: 100) { edges { node { id title url platform { id label } options { name probability } qualityIndicators { numForecasts volume } } } } }"}'
```

### Key Response Fields
- `node.title`, `node.url`, `node.platform.id`, `node.platform.label`
- `node.options[].name`, `node.options[].probability`
- `node.qualityIndicators.numForecasts`, `.volume`

### Already Aggregates Data From
- Metaculus, GJOpen, INFER, Hypermind, Rootclaim, Betfair
- Avoids need to integrate each individually

---

## 7. SMARKETS API (NEW - High Priority)

| Field | Value |
|-------|-------|
| **Status** | CONFIRMED WORKING |
| **Base URL** | `https://api.smarkets.com/v3` |
| **Auth** | None for reads |
| **Free?** | Yes |
| **Rate Limits** | Not published, tested reasonable |
| **Data** | Events, markets, contracts, quotes (full orderbook), last prices |
| **Markets** | Politics, sports, entertainment, current affairs (UK-based exchange) |
| **REAL MONEY** | Yes - this is a real-money betting exchange |

### Key Endpoints (All CONFIRMED WORKING)
```
GET /events/?type_domain=politics&state=upcoming&sort=id&limit=100
GET /events/{EVENT_ID}/markets/
GET /markets/{MARKET_ID}/contracts/
GET /markets/{MARKET_ID}/quotes/                    # Full orderbook
GET /markets/{MARKET_ID}/last_executed_prices/       # Last trade
```

### curl Examples
```bash
# Get upcoming political events
curl "https://api.smarkets.com/v3/events/?type_domain=politics&state=upcoming&sort=id&limit=5"

# Get markets for an event
curl "https://api.smarkets.com/v3/events/44841078/markets/"

# Get contracts (outcomes)
curl "https://api.smarkets.com/v3/markets/134826501/contracts/"

# Get orderbook quotes (CONFIRMED - returns full depth)
curl "https://api.smarkets.com/v3/markets/134826501/quotes/"
# Returns: {"378364939": {"bids": [{"price":1250,"quantity":160000}], "offers": [...]}}

# Get last traded prices
curl "https://api.smarkets.com/v3/markets/134826501/last_executed_prices/"
# Returns: {"last_executed_prices":{"134826501":[{"contract_id":"378364940","last_executed_price":"84.75"}]}}
```

### Price Format
Prices are in basis points (0-10000 scale, divide by 100 to get percentage).
- `1250` = 12.5% implied probability
- `8475` = 84.75% implied probability

### Workflow
1. `GET /events/` -> list events (politics, sports, etc.)
2. `GET /events/{id}/markets/` -> get markets for event
3. `GET /markets/{id}/contracts/` -> get outcomes
4. `GET /markets/{id}/quotes/` -> get orderbook depth

### Integration Priority: HIGH
Real-money exchange with orderbook depth, politics markets, and no auth required for reads.
Excellent for cross-platform arb detection against Polymarket/Kalshi.

---

## 8. SX BET API (NEW - Medium Priority)

| Field | Value |
|-------|-------|
| **Status** | CONFIRMED WORKING |
| **Base URL** | `https://api.sx.bet` |
| **Auth** | None for reads |
| **Free?** | Yes |
| **Data** | Active markets, orders/orderbook, sports, leagues, metadata |
| **Markets** | Sports primarily, but has politics/crypto/entertainment leagues |
| **REAL MONEY** | Yes - decentralized on SX Network (crypto) |

### Key Endpoints (All CONFIRMED WORKING)
```
GET /sports                                       # List all sports (incl. Politics, Crypto, etc.)
GET /leagues?sportId=17                           # Leagues for politics
GET /markets/active?pageSize=100                  # Active markets
GET /markets/active?sportId=17&pageSize=100       # Filter by sport
GET /markets/popular?pageSize=100                 # Popular markets
GET /orders?marketHashes={HASH}                   # Orderbook for market
GET /metadata                                     # Exchange metadata, fees
```

### curl Examples
```bash
# List all sports (includes politics=17, crypto=14, entertainment=18, economics=16)
curl "https://api.sx.bet/sports"

# Get politics leagues
curl "https://api.sx.bet/leagues?sportId=17"

# Get active markets
curl "https://api.sx.bet/markets/active?pageSize=3"

# Get orders (orderbook) for a market
curl "https://api.sx.bet/orders?marketHashes=0x8d51337f..."
```

### Key Response Fields (Markets)
- `marketHash`, `outcomeOneName`, `outcomeTwoName`, `outcomeVoidName`
- `sportLabel`, `sportId`, `leagueId`, `leagueLabel`
- `gameTime`, `status`, `liveEnabled`

### Key Response Fields (Orders)
- `orderHash`, `maker`, `totalBetSize`
- `percentageOdds` (18-decimal format: `70375000000000000000` = 70.375%)
- `isMakerBettingOutcomeOne`, `fillAmount`

### Sport IDs for Non-Sports Markets
```
10 = Novelty Markets
14 = Crypto
16 = Economics
17 = Politics (leagues: POTUS, Trump, US Midterms, Pop Culture)
18 = Entertainment
23 = NFTs
27 = Degen Crypto
```

### Integration Note
Markets are primarily sports-focused. Non-sports markets (politics, crypto) exist but may
have low liquidity. Odds are in 18-decimal format (divide by 1e18 to get probability).
Currently, political markets return empty results, suggesting they may be seasonal
(active during election cycles).

---

## 9. AZURO PROTOCOL (NEW - Medium Priority)

| Field | Value |
|-------|-------|
| **Status** | CONFIRMED WORKING (Gnosis chain + Polygon chain + Chiliz) |
| **Base URL** | `https://thegraph.azuro.org/subgraphs/name/azuro-protocol/azuro-api-gnosis-v3` |
| **Alt URLs** | `.../azuro-api-polygon-v3`, `.../azuro-api-chiliz-v3` |
| **Auth** | None |
| **Free?** | Yes (The Graph subgraph) |
| **Data** | Games, conditions, outcomes with decimal odds |
| **Markets** | Sports (Football, Hockey, Baseball, CS2, etc.) |
| **REAL MONEY** | Yes - decentralized on-chain |

### curl Example
```bash
curl -X POST "https://thegraph.azuro.org/subgraphs/name/azuro-protocol/azuro-api-gnosis-v3" \
  -H "Content-Type: application/json" \
  -d '{"query":"{ conditions(first:5) { conditionId status outcomes { outcomeId currentOdds } } }"}'
```

### Response Format
```json
{
  "data": {
    "conditions": [{
      "conditionId": "1006...",
      "status": "Created",
      "outcomes": [
        {"outcomeId": "9172", "currentOdds": "1.612311500727"},
        {"outcomeId": "9173", "currentOdds": "2.225728120118"}
      ]
    }]
  }
}
```

### Key Fields
- `currentOdds` = decimal odds (1/odds = implied probability)
- `status` = Created, Resolved, Canceled
- Games include title, sport, league info

### Integration Note
Primarily sports-focused. Useful for sports arb detection against traditional bookmakers.
Multiple chains available (Gnosis, Polygon, Chiliz). Arbitrum endpoint not found.

---

## 10. METACULUS API (Requires Free Auth)

| Field | Value |
|-------|-------|
| **Status** | REQUIRES AUTH (free account) |
| **Base URL** | `https://www.metaculus.com/api2/questions/` |
| **Auth** | API token required (free account registration) |
| **Free?** | Yes with free account |
| **Data** | Forecasting probabilities, community predictions, resolution dates |
| **Markets** | Science, AI, geopolitics, economics (forecasting, not betting) |

### How to Get Token
1. Create free account at metaculus.com
2. Get API token from account settings
3. Pass as `Authorization: Token {YOUR_TOKEN}` header

### curl Example (with auth)
```bash
curl "https://www.metaculus.com/api2/questions/?limit=10&status=open&type=forecast" \
  -H "Authorization: Token YOUR_API_TOKEN"
```

### Integration Note
Metaculus data is ALREADY available via Metaforecast aggregator (source #6).
Direct integration only needed if you want more granular data (community vs.
prediction breakdown, time series of forecasts, question metadata).

---

## 11. ELECTION BETTING ODDS (Not Viable as API)

| Field | Value |
|-------|-------|
| **Status** | NO API - scraping only |
| **URL** | `https://electionbettingodds.com` |
| **Data** | Aggregated odds from Betfair, PredictIt, Smarkets, Polymarket |

### Note
This is a static HTML site with no JSON API. Data would need to be scraped.
Since it aggregates from platforms we already integrate directly, there is
minimal value in scraping it.

---

## 12. GOOD JUDGMENT OPEN (Available via Metaforecast)

| Field | Value |
|-------|-------|
| **Status** | NO DIRECT API (available via Metaforecast) |
| **URL** | `https://www.gjopen.com` |
| **Direct API** | Returns empty response (curl returns nothing) |
| **Indirect** | Metaforecast includes GJOpen data as `goodjudgmentopen` platform |

---

## 13. INFER / RAND Forecasting (Requires Auth)

| Field | Value |
|-------|-------|
| **Status** | REQUIRES AUTH (OAuth bearer token) |
| **Old URL** | `https://www.infer-pub.com/api/v1/questions` |
| **New URL** | `https://www.randforecastinginitiative.org/api/v1/questions` |
| **Auth** | OAuth2 Bearer token required |
| **Indirect** | Available via Metaforecast as `infer` platform |

---

## 14. HYPERMIND (Available via Metaforecast)

| Field | Value |
|-------|-------|
| **Status** | NO PUBLIC API (403 Forbidden) |
| **URL** | `https://predict.hypermind.com` |
| **Indirect** | Available via Metaforecast as `hypermind` platform |

---

## 15. ROBINHOOD EVENT CONTRACTS (No Public API)

| Field | Value |
|-------|-------|
| **Status** | NO PUBLIC API |
| **Tested** | `https://bonfire.robinhood.com/instruments/event-contracts/` -> 404 |
| **Tested** | `https://api.robinhood.com/event-contracts/` -> 404 |
| **Note** | Robinhood has event contracts in their app but no discoverable public API |

---

## 16. CRYPTO.COM PREDICTIONS (No API)

| Field | Value |
|-------|-------|
| **Status** | NO API |
| **Note** | Returns HTML SPA, no JSON endpoint found. Prediction features appear to be in-app only. |

---

## 17. ZEITGEIST (Dead)

| Field | Value |
|-------|-------|
| **Status** | DEAD - SSL certificate expired |
| **URL** | `https://processor.rpc-0.zeitgeist.pm/graphql` |
| **Error** | `SEC_E_CERT_EXPIRED` |
| **Note** | Polkadot prediction market appears defunct |

---

## 18. BETFAIR EXCHANGE (Blocked - Requires App Key)

| Field | Value |
|-------|-------|
| **Status** | BLOCKED (Cloudflare, requires app key) |
| **URL** | `https://api.betfair.com/exchange/betting/rest/v1.0/` |
| **Auth** | Requires registered app key + session token |
| **Free?** | Free tier exists (limited requests) |
| **Indirect** | Available via Metaforecast as `betfair` platform |
| **Note** | Not accessible from US without VPN due to geo-restrictions |

---

## 19. OVERTIME MARKETS / THALES (Down)

| Field | Value |
|-------|-------|
| **Status** | 503 Service Unavailable |
| **URL** | `https://api.thalesmarket.io/overtime/networks/10/markets` |
| **Note** | Decentralized sports market on Optimism. API appears intermittently down. |

---

## 20. IOWA ELECTRONIC MARKETS (No Active Markets)

| Field | Value |
|-------|-------|
| **Status** | DEAD - No active markets |
| **URL** | `https://iemweb.biz.uiowa.edu` |
| **Note** | Academic prediction market, appears to have no 2028 markets yet. |

---

## 21. COINGECKO (Supplementary)

| Field | Value |
|-------|-------|
| **Status** | CONFIRMED WORKING |
| **Base URL** | `https://api.coingecko.com/api/v3` |
| **Auth** | None for free tier |
| **Free?** | Yes (10-30 req/min) |
| **Data** | Crypto spot prices - useful for validating crypto prediction markets |

```bash
curl "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"
# Returns: {"bitcoin":{"usd":68949}}
```

---

## PRIORITY INTEGRATION RECOMMENDATIONS

### Tier 1 - Integrate Immediately (High Value, Free, Working)
1. **Polymarket CLOB API** - Adds orderbook depth to existing Polymarket integration. Get TRUE executable prices instead of indicative midpoints. Zero additional cost.
2. **Smarkets API** - REAL MONEY exchange with politics markets. Full orderbook depth. No auth. Excellent arb partner for Polymarket/Kalshi.
3. **Kalshi URL Update** - Current URL `trading-api.kalshi.com` returns redirect. Update to `api.elections.kalshi.com`. Also add orderbook endpoint.

### Tier 2 - Integrate Next (Moderate Value)
4. **SX Bet API** - Decentralized exchange with politics/crypto leagues. Sports-heavy but has non-sports categories. Orderbook via `/orders`.
5. **Azuro Protocol** - Decentralized sports odds on multiple chains. Good for sports arb detection.

### Tier 3 - Already Covered via Metaforecast
6. **Metaculus** - Already in Metaforecast. Direct integration only if you need time-series data (requires free account).
7. **Good Judgment Open** - In Metaforecast as `goodjudgmentopen`
8. **INFER** - In Metaforecast as `infer`
9. **Hypermind** - In Metaforecast as `hypermind`
10. **Betfair** - In Metaforecast as `betfair`

### Not Worth Integrating
- Robinhood (no API), Crypto.com (no API), Zeitgeist (dead), IEM (no active markets)
- Election Betting Odds (scraping only, aggregates sources we already have)
- Overtime/Thales (currently down)

---

## KALSHI CONSTANTS.PY FIX NEEDED

The Kalshi API has moved. The old URL still technically works but returns a warning.
Update `backend/constants.py`:

```python
# BEFORE (redirects with warning):
KALSHI_API_BASE = "https://trading-api.kalshi.com/trade-api/v2"

# AFTER (correct current URL):
KALSHI_API_BASE = "https://api.elections.kalshi.com/trade-api/v2"
```

---

## PLATFORM FEE STRUCTURES (For new platforms)

```python
PLATFORM_FEES.update({
    "smarkets": {
        "trade_fee": 0.02,       # 2% commission on net winnings
        "withdrawal_fee": 0.00,
        "profit_fee": 0.00,
    },
    "sx_bet": {
        "trade_fee": 0.00,       # 0% maker fee
        "withdrawal_fee": 0.00,  # Crypto withdrawals
        "profit_fee": 0.00,
    },
    "azuro": {
        "trade_fee": 0.05,       # ~5% margin built into odds
        "withdrawal_fee": 0.00,
        "profit_fee": 0.00,
    },
})
```
