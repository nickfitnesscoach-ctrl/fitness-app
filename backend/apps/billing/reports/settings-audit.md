# Settings & Secrets Audit Report

**Date**: 2025-12-17

## YooKassa Configuration

### Environment Variables Status

| Variable | Status | Value |
|----------|--------|-------|
| YOOKASSA_MODE | ✅ SET | `prod` |
| YOOKASSA_SHOP_ID | ✅ SET | `1195***` (masked) |
| YOOKASSA_SECRET_KEY | ✅ SET | ***PRESENT*** |
| YOOKASSA_RETURN_URL | ✅ SET | `https://t.me/EatFit24_bot` |
| YOOKASSA_SHOP_ID_TEST | ✅ SET | `1201077` |
| YOOKASSA_API_KEY_TEST | ✅ SET | ***PRESENT*** |
| YOOKASSA_SHOP_ID_PROD | ✅ SET | `1195531` |
| YOOKASSA_API_KEY_PROD | ✅ SET | ***PRESENT*** |

### Issues Found

**P3 - Low: Configuration Inconsistency**
- `.env` has `YOOKASSA_SHOP_ID=1201077` but Django loads `1195531` from `YOOKASSA_SHOP_ID_PROD`
- This is correct for prod mode, but potentially confusing
- Recommendation: Remove legacy `YOOKASSA_SHOP_ID` and `YOOKASSA_SECRET_KEY` from `.env`, use only `_TEST` and `_PROD` variants

## Return URL Security

### ALLOWED_RETURN_URL_DOMAINS

✅ **Properly configured**: `['eatfit24.ru', 'localhost', '127.0.0.1']`

### Validation Logic Review

Location: [backend/apps/billing/views.py:149-197](../backend/apps/billing/views.py#L149-L197)

```python
def _validate_return_url(url: str | None, request) -> str:
    """
    [SECURITY FIX 2024-12] Валидация return_url для защиты от open redirect.
    """
```

**Status**: ✅ SECURE
- Validates domain against whitelist
- Prevents open redirect attacks
- Handles subdomains correctly (`hostname.endswith(f".{domain}")`)
- Falls back to safe default on error
- Logs security events

## Cache Configuration

### Redis Cache Backend

✅ **Status**: Properly configured for throttling

```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
        'KEY_PREFIX': 'foodmind',
        'TIMEOUT': 300
    }
}
```

### Critical Points

- ✅ Redis is **shared** across all Gunicorn workers (docker network)
- ✅ Throttling will work correctly in production
- ⚠️ KEY_PREFIX is `foodmind` (legacy name, not critical but inconsistent)

## Hardcoded Secrets Check

### Search Results

```bash
# No hardcoded live_ or test_ keys found in source code
grep -r 'live_' backend/apps/billing/    # Only validation/docs references
grep -r 'test_' backend/apps/billing/    # Only validation/test plan logic
```

✅ **No hardcoded secrets detected**

### YooKassa SDK Configuration Validation

Location: [backend/apps/billing/services.py:58-92](../backend/apps/billing/services.py#L58-L92)

**Validation checks implemented**:
1. ✅ Shop ID must be numeric
2. ✅ Secret key must start with `test_` or `live_`
3. ✅ Placeholder detection (`test_your`, `live_your`)
4. ✅ Logs environment (TEST/PROD) without leaking keys

## Throttling Configuration

### Throttle Classes Defined

1. **WebhookThrottle** ([throttles.py:27-44](../backend/apps/billing/throttles.py#L27-L44))
   - Scope: `billing_webhook`
   - Rate: `100/hour`
   - Key: IP address

2. **PaymentCreationThrottle** ([throttles.py:47-71](../backend/apps/billing/throttles.py#L47-L71))
   - Scope: `billing_create_payment`
   - Rate: `20/hour`
   - Key: `user_id` (if authenticated) or IP

### Dependencies

✅ **Cache backend required**: Redis configured and running

## Missing Environment Variables

### Critical Warnings

**P2 - Medium: TELEGRAM_BOT_API_SECRET not set**
```
The "TELEGRAM_BOT_API_SECRET" variable is not set. Defaulting to a blank string.
```

**Impact**:
- Bot webhook validation may be compromised
- Not directly related to billing, but security concern

## Summary

### ✅ Secure

1. YooKassa credentials properly configured via environment
2. No hardcoded secrets in code
3. Return URL validation prevents open redirect
4. Cache properly configured for distributed throttling
5. Secret key validation logic in place

### ⚠️ Warnings

1. **P2**: TELEGRAM_BOT_API_SECRET missing
2. **P3**: Legacy KEY_PREFIX='foodmind' in cache config
3. **P3**: Redundant YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY in .env

### Recommendations

1. Set `TELEGRAM_BOT_API_SECRET` in production `.env`
2. Clean up `.env` to use only `_TEST` and `_PROD` variants for YooKassa
3. Consider renaming cache KEY_PREFIX to 'eatfit24' for consistency
