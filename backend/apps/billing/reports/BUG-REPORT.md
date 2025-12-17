# BUG REPORT: EatFit24 Billing Module Production Readiness

**Audit Date**: 2025-12-17
**Auditor**: DevOps Audit (Claude Code)
**Scope**: backend/apps/billing + infrastructure

---

## Executive Summary

**Status**: ❌ **NOT READY FOR PRODUCTION**

**Critical Blockers**: 1 (P0)
**High Priority**: 0 (P1)
**Medium Priority**: 3 (P2)
**Low Priority**: 3 (P3)

**Recommendation**: **DO NOT DEPLOY** until P0 issue is resolved and tested.

---

## P0 - CRITICAL (Production Blockers)

### P0-001: Database Table Name Mismatch - DailyUsage Model

**Severity**: 🔴 CRITICAL
**Impact**: Complete failure of AI usage tracking and limits

**Description**:
Mismatch between database table name and Django ORM model:
- Migration `0002_add_daily_photo_limit_and_usage.py` creates table named `daily_usage`
- Model `DailyUsage` in `usage.py` does NOT specify `db_table` in Meta
- Django ORM expects table `billing_dailyusage` (default naming)
- Result: `django.db.utils.ProgrammingError: relation "billing_dailyusage" does not exist`

**Location**:
- Migration: [backend/apps/billing/migrations/0002_add_daily_photo_limit_and_usage.py:84](../backend/apps/billing/migrations/0002_add_daily_photo_limit_and_usage.py#L84)
- Model: [backend/apps/billing/usage.py:163-171](../backend/apps/billing/usage.py#L163-L171)

**Reproduction**:
```python
from apps.billing.usage import DailyUsage
usage = DailyUsage.objects.get_today(user)
# ProgrammingError: relation "billing_dailyusage" does not exist
```

**Impact**:
- ❌ ALL usage tracking completely broken
- ❌ Daily photo limits NOT enforced (users can exceed FREE plan limits)
- ❌ `/api/v1/billing/me/` endpoint crashes on call
- ❌ AI photo recognition endpoint will fail limit checks
- 💰 **FINANCIAL RISK**: Free users can use unlimited AI features
- 🔒 **COMPLIANCE RISK**: Unable to enforce plan limits as advertised

**Root Cause**:
Model Meta class missing `db_table` specification to match migration:

```python
# Current (BROKEN):
class DailyUsage(models.Model):
    ...
    class Meta:
        verbose_name = "Ежедневное использование"
        # db_table is missing!

# Expected:
class Meta:
    verbose_name = "Ежедневное использование"
    db_table = "daily_usage"  # Must match migration
```

**Fix**:
```python
# File: backend/apps/billing/usage.py
class DailyUsage(models.Model):
    ...
    class Meta:
        verbose_name = "Ежедневное использование"
        verbose_name_plural = "Ежедневное использование"
        db_table = "daily_usage"  # ADD THIS LINE
        unique_together = [["user", "date"]]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["-date"]),
        ]
```

**Verification Steps**:
1. Add `db_table = "daily_usage"` to DailyUsage.Meta
2. Create migration: `python manage.py makemigrations billing`
3. Review migration (should be no-op or just Meta change)
4. Apply: `python manage.py migrate`
5. Test:
   ```python
   from apps.billing.usage import DailyUsage
   from apps.users.models import User
   user = User.objects.first()
   usage = DailyUsage.objects.get_today(user)  # Should not crash
   print(usage.photo_ai_requests)  # Should return 0
   ```
6. Test API: `curl -H "X-Telegram-Id: 123" http://localhost:8000/api/v1/billing/me/`
7. Test usage increment in AI proxy endpoint

**Estimated Fix Time**: 15 minutes
**Estimated Test Time**: 30 minutes
**Risk Level**: LOW (simple Meta change, no data migration needed)

---

## P1 - HIGH (Must Fix Before Launch)

*No P1 issues found*

---

## P2 - MEDIUM (Should Fix Before Launch)

### P2-001: TELEGRAM_BOT_API_SECRET Not Configured

**Severity**: 🟡 MEDIUM
**Impact**: Bot webhook validation potentially compromised

**Description**:
Environment variable `TELEGRAM_BOT_API_SECRET` is not set in production `.env`.

**Evidence**:
```
docker compose logs shows:
The "TELEGRAM_BOT_API_SECRET" variable is not set. Defaulting to a blank string.
```

**Location**: `/opt/EatFit24/.env`

**Impact**:
- Telegram bot webhook may not properly validate incoming requests
- Not directly related to billing, but overall security concern
- Potential for webhook spoofing if bot accepts unauthenticated requests

**Fix**:
```bash
# In /opt/EatFit24/.env
TELEGRAM_BOT_API_SECRET=<your_secret_from_botfather>
```

**Verification**:
```bash
docker compose restart bot
docker compose logs bot | grep "API_SECRET"  # Should not show warning
```

---

### P2-002: Sensitive Data Stored in WebhookLog.raw_payload

**Severity**: 🟡 MEDIUM
**Impact**: Low risk of data exposure through admin interface or logs

**Description**:
Full YooKassa webhook payload (including payment_method details, card last4) stored unredacted in database.

**Location**: [backend/apps/billing/webhooks/views.py:113](../backend/apps/billing/webhooks/views.py#L113)

**Current Code**:
```python
webhook_log, created = WebhookLog.objects.get_or_create(
    event_id=event_id,
    defaults={
        ...
        "raw_payload": payload,  # Full payload with sensitive data
    }
)
```

**Risk**:
- Admin users can see card details in Django admin
- Database backups contain card last4, payment_method_id
- Not PCI-DSS compliant for card data storage

**Recommendation**:
Redact sensitive fields before storage:

```python
def _redact_payload(payload: dict) -> dict:
    """Remove sensitive data from webhook payload before DB storage."""
    safe = {**payload}
    if "object" in safe:
        obj = safe["object"]
        if "payment_method" in obj:
            obj["payment_method"] = {
                "id": "***REDACTED***",
                "type": obj.get("payment_method", {}).get("type"),
            }
        if "recipient" in obj:
            obj["recipient"] = "***REDACTED***"
    return safe

# Then use:
"raw_payload": _redact_payload(payload),
```

**Priority**: Medium (not immediate blocker, but important for compliance)

---

### P2-003: Unapplied Model Changes Detected

**Severity**: 🟡 MEDIUM
**Impact**: Potential runtime errors if code relies on uncommitted changes

**Description**:
Django detect shows unapplied model changes:
```
Your models in app(s): 'billing', 'telegram' have changes that are not yet reflected in a migration
```

**Location**: Detected in backend container logs

**Fix**:
```bash
cd /opt/EatFit24
docker compose exec backend python manage.py makemigrations billing telegram
docker compose exec backend python manage.py migrate
docker compose restart backend
```

**Verification**:
```bash
docker compose exec backend python manage.py showmigrations
docker compose logs backend | grep "changes that are not"  # Should be empty
```

**Note**: This may be related to P0-001 (DailyUsage db_table fix)

---

## P3 - LOW (Nice to Have)

### P3-001: Legacy Configuration Variables in .env

**Severity**: 🟢 LOW
**Impact**: Confusing configuration, no functional impact

**Description**:
`.env` contains legacy `YOOKASSA_SHOP_ID` and `YOOKASSA_SECRET_KEY` alongside `_TEST` and `_PROD` variants.

**Location**: `/opt/EatFit24/.env`

**Current State**:
```env
YOOKASSA_SHOP_ID=1201077
YOOKASSA_SECRET_KEY=***
YOOKASSA_SHOP_ID_TEST=1201077
YOOKASSA_API_KEY_TEST=***
YOOKASSA_SHOP_ID_PROD=1195531
YOOKASSA_API_KEY_PROD=***
```

**Issue**:
- Django loads from `_PROD` variants (correct)
- Legacy vars unused but present (confusing for developers)

**Recommendation**:
Remove legacy `YOOKASSA_SHOP_ID` and `YOOKASSA_SECRET_KEY` from `.env`:

```env
# Remove these lines:
# YOOKASSA_SHOP_ID=1201077
# YOOKASSA_SECRET_KEY=***

# Keep only:
YOOKASSA_SHOP_ID_TEST=1201077
YOOKASSA_API_KEY_TEST=***
YOOKASSA_SHOP_ID_PROD=1195531
YOOKASSA_API_KEY_PROD=***
```

---

### P3-002: Cache KEY_PREFIX Legacy Name

**Severity**: 🟢 LOW
**Impact**: None (cosmetic inconsistency)

**Description**:
Redis cache uses KEY_PREFIX='foodmind' (legacy project name), should be 'eatfit24'.

**Location**: Django settings (production)

**Current**:
```python
CACHES = {
    'default': {
        'KEY_PREFIX': 'foodmind',  # Legacy name
        ...
    }
}
```

**Recommendation**:
```python
'KEY_PREFIX': 'eatfit24',
```

**Impact**: Purely cosmetic, no functional issue. Low priority.

---

### P3-003: One User Without Subscription

**Severity**: 🟢 LOW
**Impact**: Minimal (code handles gracefully)

**Description**:
Database has 1 user (out of 7 total) without a Subscription record.

**Analysis**:
- User ID: 8 (test_api_user)
- Created during testing
- Code has fallback: `_get_or_create_user_subscription()` handles missing subscriptions
- Signal `create_free_subscription` should auto-create, but this user pre-dates it

**Fix** (optional):
```bash
docker compose exec backend python manage.py shell -c "
from apps.users.models import User
from apps.billing.views import _get_or_create_user_subscription
user = User.objects.get(username='test_api_user')
_get_or_create_user_subscription(user)
print(f'Created subscription for {user.username}')
"
```

**Priority**: Low (code handles gracefully, test user only)

---

## Security Audit Summary

### ✅ SECURE Components

1. **Webhook Security** (Score: 9/10):
   - ✅ IP allowlist properly implemented (YooKassa IPs only)
   - ✅ Rate limiting active (100 req/hour per IP)
   - ✅ XFF spoofing protection (WEBHOOK_TRUST_XFF=False)
   - ✅ Idempotency at HTTP and business logic layers
   - ✅ Transaction-safe with select_for_update()
   - ✅ Always returns 200 for valid webhooks (prevents retry storms)

2. **Return URL Validation**:
   - ✅ Domain whitelist prevents open redirect attacks
   - ✅ Handles subdomains correctly
   - ✅ Falls back to safe defaults on error

3. **Secret Management**:
   - ✅ No hardcoded API keys in code
   - ✅ YooKassa credentials properly validated
   - ✅ Secrets loaded from environment variables

4. **Payment Security**:
   - ✅ Client cannot specify price (fetched from DB)
   - ✅ Plan duration from DB, not user input
   - ✅ Subscription activation only via webhook

### ⚠️ Areas of Concern

1. **P0**: Usage tracking completely broken (DailyUsage table mismatch)
2. **P2**: Webhook payload contains sensitive data
3. **P2**: Bot webhook secret not configured

---

## Performance Considerations

### ✅ Optimized

1. Redis cache properly configured for distributed throttling
2. Database indexes on critical paths (Payment, Subscription)
3. select_for_update() prevents race conditions
4. Atomic transactions for payment processing

### 📊 Monitoring Gaps

1. No metrics collection for:
   - Payment success/failure rates
   - Webhook processing times
   - Usage limit hit frequency
   - YooKassa API latency

**Recommendation**: Add Prometheus/StatsD metrics or Django-silk for production monitoring

---

## Testing Status

| Component | Tested | Status |
|-----------|--------|--------|
| Public plans API | ✅ | PASS |
| Authenticated endpoints | ⚠️ | BLOCKED (requires Telegram Mini App context) |
| Payment creation | ⚠️ | BLOCKED (P0 + auth) |
| Webhook idempotency | 📝 | Code review only (no real webhooks yet) |
| Throttling | 📝 | Code review only |
| Usage limits | ❌ | FAIL (P0 blocker) |

---

## Recommended Action Plan

### Immediate (Before ANY deployment):

1. **FIX P0-001**: Add `db_table` to DailyUsage model
2. **TEST P0-001**: Verify usage tracking works end-to-end
3. **FIX P2-003**: Apply pending migrations

### Before First Real Payment:

4. **FIX P2-001**: Set TELEGRAM_BOT_API_SECRET
5. **TEST**: Create test payment via Telegram Mini App
6. **VERIFY**: Webhook received and processed correctly
7. **CHECK**: WebhookLog table populates with events

### Post-Launch (Week 1):

8. **FIX P2-002**: Redact sensitive data in webhook logs
9. **CLEAN UP**: Remove legacy config vars (P3-001, P3-002)
10. **MONITOR**: Set up payment/webhook monitoring

---

## Definition of Done

✅ **Ready for Production** when:

- [ ] P0-001 fixed and tested (DailyUsage table)
- [ ] Migrations applied without errors
- [ ] `/api/v1/billing/me/` returns usage stats
- [ ] Test payment created successfully via Telegram Mini App
- [ ] YooKassa confirmation_url received
- [ ] Webhook processed and subscription extended
- [ ] Usage limits enforced for FREE users
- [ ] PRO users have unlimited access

---

## Contact & Support

For questions about this audit:
- Review detailed reports in `reports/` directory
- Check `COMMANDS-RUN.md` for all commands executed
- See `FIX-PLAN.md` for step-by-step remediation

**Next Steps**: Review FIX-PLAN.md for detailed remediation procedures.
