# ArbitrageIQ Bug Report — April 7, 2026

## Test Results Summary

| Test | Result | Issue |
|------|--------|-------|
| Ping | PASS | |
| Categories | PASS | 7 categories |
| Pricing | PASS | 3 plans with correct prices |
| Set Category | PASS | |
| Invalid Category | PASS | |
| Health | PASS | 6/7 healthy |
| Data Sources | WARN | Only 2 sources active (polymarket 262, predictit 743) |
| Auth/Me | FAIL | role=None, tier=None despite being admin |
| Premium Gating | FAIL | premium=False for authenticated admin user |
| Admin Stats | FAIL | Auth token not working, returns empty |
| Alert Settings | FAIL | Returns None for all fields |
| Bet Tracker Create | FAIL | Auth token not recognized |
| Bet Summary | FAIL | Auth token not recognized |
| History | WARN | 0 entries (may need more detection cycles) |
| Analytics | FAIL | Auth token not recognized |
| SX Bet | FAIL | 115 consecutive failures, permanently degraded |
| Free Tier Gating | PARTIAL | Shows blurred_count=32, but premium=False even for logged in user |

---

## Bug 1: Auth Token Not Working — User Fields Return None
**Severity:** CRITICAL
**Impact:** All authenticated features broken (admin, alerts, bets, analytics)

**Root Cause:** The user was registered in the PostgreSQL database before the `role`, `telegram_chat_id`, `discord_webhook_url`, `alert_min_profit`, `alerts_enabled` columns were added to the User model. PostgreSQL created these columns with NULL instead of defaults because the rows already existed. The `/api/auth/me` endpoint returns role=None and tier=None, which makes the premium check fail.

**Fix:**
1. In `routes.py` auth/me endpoint: default `role` to "user" if None
2. In `routes.py` auth/me endpoint: default `subscription_tier` to "free" if None
3. Re-run `/api/admin/make-admin` to reset the admin user's role and tier
4. Add migration-safe defaults: `user.role = user.role or "user"` in all auth checks

---

## Bug 2: Smarkets Data Not Appearing in Active Prices
**Severity:** HIGH
**Impact:** Smarkets arbs not detected, reduces opportunities from 50 to 2

**Root Cause:** Smarkets shows "healthy" in health check but 0 active prices. The `_trigger_fetch_cycle` runs Smarkets, but the data may not persist correctly due to:
1. Smarkets API rate limiting during rapid fetch cycle
2. Category filter rejecting Smarkets markets (political markets on Smarkets use different naming that may not match our KEYWORD_MAP)
3. The Smarkets parent event IDs may not have active child markets currently

**Fix:**
1. Add logging to Smarkets ingestion to show how many markets fetched vs filtered
2. Check if Smarkets political parent IDs are still valid
3. Relax category filtering for Smarkets — many political markets may not contain keywords
4. Test Smarkets fetch independently with debug output

---

## Bug 3: Metaforecast Data Not Appearing in Active Prices
**Severity:** MEDIUM
**Impact:** No cross-source discrepancy signals, reduces consensus quality

**Root Cause:** Metaforecast shows "healthy" but its data (betfair, foretold, etc.) doesn't appear in active prices this test run. Previous test showed 26 metaforecast prices. May be timing — the scheduled fetch may not have run yet.

**Fix:**
1. Ensure `fetch_metaforecast` is in the `_trigger_fetch_cycle`
2. Add more aggressive initial fetch on category change

---

## Bug 4: SX Bet Permanently Degraded (115 failures)
**Severity:** LOW
**Impact:** No SX Bet data. Minor since SX Bet has limited political markets.

**Root Cause:** SX Bet API (`api.sx.bet`) may be returning errors or have changed their endpoint structure. 115 consecutive failures means it's been failing since deployment.

**Fix:**
1. Check SX Bet API response manually
2. If API is down/changed, disable the scheduled job to stop wasting resources
3. Add circuit breaker: after 10 consecutive failures, pause for 1 hour before retrying

---

## Bug 5: Free vs Premium Gating Inconsistent
**Severity:** HIGH
**Impact:** Free users see blurred_count=32 (correct) but premium users also see premium=False

**Root Cause:** The `get_optional_user()` function extracts the JWT from the Authorization header. If the token is valid but the user's `subscription_tier` is None (Bug 1), the premium check fails. The admin user who should have "monthly" tier has None in the database.

**Fix:** Same as Bug 1 — fix the auth/me defaults and re-apply admin status.

---

## Bug 6: Missing Market URLs for Smarkets and Betfair Legs
**Severity:** MEDIUM
**Impact:** Users can't click through to the market on these platforms

**Root Cause:** 
- Smarkets: `_build_market_url` in scheduler.py doesn't have a Smarkets handler, so URL is empty
- Betfair: Same — no URL handler for betfair source

**Fix:**
1. Add Smarkets URL handler: `https://smarkets.com/event/{event_id}`
2. Add Betfair URL handler: `https://www.betfair.com` (no deep links available)
3. For Metaforecast sources: use the `metadata_.url` field if available

---

## Bug 7: Arb History Empty Despite Active Arbs
**Severity:** LOW
**Impact:** History and analytics features have no data to show

**Root Cause:** The arb history tracking was just added. It runs inside `run_arb()` which executes every 120 seconds. If the test was run before a detection cycle completed, history would be empty. Should populate after 2-3 cycles.

**Fix:** No code fix needed — this is a timing issue. History will populate over time. However, should add a "last_detected_at" field to the analytics response so users know when the last scan completed.

---

## Bug 8: Login Response Missing Role Field
**Severity:** MEDIUM  
**Impact:** Frontend doesn't know user is admin until /auth/me is called

**Root Cause:** The `POST /api/auth/login` response includes `id`, `email`, `subscription_tier`, `subscription_expires_at` but does NOT include `role`. The frontend needs `role` to show the ADMIN button.

**Fix:** Add `"role": user.role or "user"` to the login response dict.

---

## Fix Priority Order

| # | Bug | Effort | Impact |
|---|-----|--------|--------|
| 1 | Auth defaults (role=None, tier=None) | 15 min | CRITICAL — unblocks everything |
| 2 | Login response missing role field | 5 min | HIGH — admin button |
| 3 | Free/premium gating fix | 5 min | HIGH — paywall works |
| 4 | Smarkets data not appearing | 30 min | HIGH — restores 50 arbs |
| 5 | Missing market URLs | 15 min | MEDIUM — UX |
| 6 | Metaforecast timing | 10 min | MEDIUM |
| 7 | SX Bet circuit breaker | 15 min | LOW |
| 8 | Arb history timing | 0 min | LOW — self-resolving |

**Total fix effort: ~1.5 hours**

---

## Fix Implementation Plan

### Fix 1: Auth Defaults (CRITICAL)
**File: `backend/src/api/routes.py`**

In `get_me()`, `login()`, and `get_opportunities()`:
```python
# Before returning user data, default None fields
tier = user.subscription_tier or "free"
role = user.role or "user"
```

In `get_opportunities()` premium check:
```python
# Treat admin/employee as premium even if tier is None
if user and (user.role in ("admin", "employee") or user.subscription_tier not in (None, "free")):
    is_premium = True
```

After fixing, re-run make-admin:
```
curl -X POST .../api/admin/make-admin -d '{"email":"jakespencer6596@gmail.com","secret":"..."}'
```

### Fix 2: Login Response Role
**File: `backend/src/api/routes.py`**

In `login()` response:
```python
return {
    "token": token,
    "user": {
        "id": user.id,
        "email": user.email,
        "role": user.role or "user",  # ADD THIS
        "subscription_tier": tier,
        ...
    },
}
```

### Fix 3: Premium Gating
**File: `backend/src/api/routes.py`**

In `get_opportunities()`:
```python
if user:
    if user.role in ("admin", "employee"):
        is_premium = True
    elif user.subscription_tier and user.subscription_tier != "free":
        if not user.subscription_expires_at or user.subscription_expires_at >= now:
            is_premium = True
```

### Fix 4: Smarkets Data
**File: `backend/src/ingestion/smarkets.py`**

1. Add debug logging to show exact API responses
2. Check if parent event IDs (924650, 44136685, etc.) return child events
3. If political events have markets, check category filter
4. Possible fix: override category to "politics" for all Smarkets political parent events

### Fix 5: Market URLs
**File: `backend/scheduler.py`** — `_build_market_url()`

Add handlers:
```python
if src == "smarkets":
    if metadata_ and isinstance(metadata_, dict):
        url = metadata_.get("url", "")
        if url: return url
    return "https://smarkets.com"

if src in ("betfair", "foretold", "givewellopenphil", "fantasyscotus", "gjopen", "infer", "hypermind"):
    if metadata_ and isinstance(metadata_, dict):
        url = metadata_.get("url", "")
        if url: return url
    return ""  # No deep link available for reference-only sources
```

### Fix 6: Metaforecast Timing
**File: `backend/src/api/routes.py`** — `_trigger_fetch_cycle()`

Ensure `fetch_metaforecast` is called and wait slightly between jobs.

### Fix 7: SX Bet Circuit Breaker
**File: `backend/src/ingestion/sxbet.py`**

Add check at start of `fetch()`:
```python
# Circuit breaker: if 10+ failures, skip for this cycle
db = SessionLocal()
status = db.query(SystemStatus).filter(SystemStatus.source == "sxbet").first()
if status and (status.consecutive_failures or 0) >= 10:
    logger.info("SX Bet: circuit breaker active (10+ failures), skipping")
    return []
```
