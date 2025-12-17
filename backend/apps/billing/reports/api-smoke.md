# API Smoke Tests Report

**Date**: 2025-12-17
**Status**: ⚠️ **CRITICAL ISSUES FOUND**

## Test Environment

- **Server**: eatfit24.ru
- **Backend**: http://localhost:8000 (internal)
- **Authentication**: Telegram-based (no JWT in production)

## Critical Blocker Found

### P0 - CRITICAL: Missing Database Table

**Issue**: `billing_dailyusage` table does not exist

**Error**:
```
django.db.utils.ProgrammingError: relation "billing_dailyusage" does not exist
```

**Impact**:
- ❌ AI photo usage tracking BROKEN
- ❌ Daily limits NOT enforced
- ❌ Users can exceed limits without being blocked
- ❌ `/api/v1/billing/me/` endpoint will crash when called

**Root Cause**:
- Unapplied migrations detected in logs: "Your models in app(s): 'billing', 'telegram' have changes that are not yet reflected in a migration"
- DailyUsage model exists in code but table missing in database

**Fix Required**:
```bash
cd /opt/EatFit24
docker compose exec backend python manage.py makemigrations billing telegram
docker compose exec backend python manage.py migrate
docker compose restart backend
```

**BLOCKER**: This MUST be fixed before production use.

## Test Results

### 1. GET /api/v1/billing/plans/ (Public, No Auth)

✅ **PASSED**

**Response** (truncated):
```json
[
  {
    "code": "FREE",
    "display_name": "Бесплатный",
    "price": "0.00",
    "duration_days": 0,
    "daily_photo_limit": 3,
    "history_days": 7,
    "ai_recognition": true,
    "advanced_stats": false,
    "priority_support": false
  },
  {
    "code": "PRO_MONTHLY",
    "display_name": "PRO месяц",
    "price": "299.00",
    "duration_days": 30,
    "daily_photo_limit": null,
    ...
  },
  {
    "code": "PRO_YEARLY",
    "display_name": "PRO год",
    "price": "2490.00",
    "duration_days": 365,
    ...
  }
]
```

**Validation**:
- ✅ Returns all active plans
- ✅ Excludes `TEST_LIVE` plan (is_test=True)
- ✅ Proper pricing and limits
- ✅ No authentication required

### 2. GET /api/v1/billing/me/ (Auth Required)

❌ **BLOCKED** - Cannot test due to DailyUsage table missing

**Expected**: Current plan, daily limits, usage stats

**Actual**: Would crash with ProgrammingError

### 3. GET /api/v1/billing/subscription/ (Auth Required)

⚠️ **UNABLE TO TEST** - Authentication issue

**Issue**: Production uses TelegramHeaderAuthentication, not JWT

**REST_FRAMEWORK settings**:
```python
DEFAULT_AUTHENTICATION_CLASSES = [
    'apps.telegram.auth.authentication.DebugModeAuthentication',  # DEV only
    'apps.telegram.auth.authentication.TelegramHeaderAuthentication'  # Requires TELEGRAM_HEADER_AUTH_ENABLED=True
]
```

**Finding**:
- JWT authentication NOT enabled in production
- TelegramHeaderAuthentication requires `TELEGRAM_HEADER_AUTH_ENABLED=True` (currently False)
- This is by design for Telegram Mini App architecture
- External API testing requires Telegram initData signature

### 4. GET /api/v1/billing/payments/ (Auth Required)

⚠️ **UNABLE TO TEST** - Same authentication issue

### 5. POST /api/v1/billing/create-payment/ (Auth Required)

⚠️ **UNABLE TO TEST** - Blocked by authentication + DailyUsage issue

**Expected Flow**:
1. Authenticate via Telegram
2. Send: `{"plan_code": "PRO_MONTHLY"}`
3. Receive: `{"payment_id": "...", "yookassa_payment_id": "...", "confirmation_url": "https://..."}`

**Blockers**:
- Authentication requires Telegram Mini App context
- DailyUsage table missing would cause errors in some flows

## Internal Service Tests

### Subscription Service

✅ **PASSED** (partial)

**Test User**: test_monthly (ID: 6)

```python
# Subscription exists
Subscription Plan: PRO_MONTHLY
Active: True
End Date: 2026-01-14 (13 months from now)

# get_effective_plan_for_user() works
Effective Plan: PRO_MONTHLY
Daily Photo Limit: None (unlimited)
```

**Validation**:
- ✅ Subscription model works
- ✅ Plan association correct
- ✅ Expiration date set properly

### Usage Tracking Service

❌ **FAILED**

**Error**: `billing_dailyusage` table does not exist

**Impact**: All usage tracking broken

## Authentication Analysis

### Current Production Setup

**Authentication Methods** (in order):
1. `DebugModeAuthentication` - Only if `DEBUG=True` (disabled in prod)
2. `TelegramHeaderAuthentication` - Requires `TELEGRAM_HEADER_AUTH_ENABLED=True` (currently False)

**Intended Flow**:
- Frontend: Telegram Mini App
- Auth: X-Telegram-Init-Data header with signed initData
- Backend validates signature using bot token

**Issue for External Testing**:
- ❌ No JWT authentication in production
- ❌ No session authentication
- ✅ This is correct for Telegram Mini App architecture
- ⚠️ Makes external API testing difficult

**Recommendation**:
- For testing: Enable `TELEGRAM_HEADER_AUTH_ENABLED=True` temporarily
- For production: Current setup is correct (Telegram only)

## Throttling (Not Tested)

**Reason**: Cannot authenticate to test rate limits

**Configured Limits**:
- `PaymentCreationThrottle`: 20/hour per user
- `WebhookThrottle`: 100/hour per IP

**Status**: ⚠️ UNTESTED (code review passed, see [webhook-audit.md](./webhook-audit.md))

## Summary

### ✅ Working

1. Public plans endpoint returns correct data
2. Subscription model and relations intact
3. Plan pricing and limits configured correctly

### ❌ Critical Issues

1. **P0**: `billing_dailyusage` table missing - BLOCKER
2. **P0**: Unapplied migrations in billing/telegram apps
3. **P2**: Cannot perform authenticated endpoint tests without Telegram context

### 📋 Required Actions Before Production

1. **MANDATORY**:
   ```bash
   python manage.py makemigrations billing telegram
   python manage.py migrate
   python manage.py check --deploy
   ```

2. **VERIFY**:
   - Test `/api/v1/billing/me/` after migration
   - Create test payment via Telegram Mini App
   - Verify WebhookLog receives and processes payment.succeeded

3. **OPTIONAL** (for external testing):
   - Set `TELEGRAM_HEADER_AUTH_ENABLED=True` temporarily
   - Or build Telegram Mini App test harness

## Recommended Test Procedure (After Fix)

1. Apply migrations
2. Restart backend
3. Open Telegram Mini App
4. Call `/api/v1/billing/me/` - should return usage stats
5. Create test payment via `/api/v1/billing/create-test-live-payment/`
6. Verify confirmation_url received
7. Complete payment in YooKassa
8. Verify webhook received and subscription extended

## Production Readiness: ❌ **NOT READY**

**Blocking Issues**:
- P0: Missing database table (billing_dailyusage)
- P0: Unapplied migrations

**After Fix**: Run full smoke test suite via Telegram Mini App
