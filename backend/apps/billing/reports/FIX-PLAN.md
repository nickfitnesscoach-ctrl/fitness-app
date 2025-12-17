# FIX PLAN: EatFit24 Billing Module
## Step-by-Step Remediation Guide

**Plan Date**: 2025-12-17
**Target**: Production Deployment
**Estimated Total Time**: 4-6 hours (across 2-3 days)

---

## Overview

This plan addresses all issues found in the billing audit, organized by priority (P0 → P1 → P2 → P3).

**Critical Path**:
1. Fix P0 (DailyUsage table) - BLOCKING
2. Apply migrations
3. Test locally
4. Fix P2 issues
5. Deploy to staging
6. Integration tests
7. Production deployment

---

## PHASE 1: Critical Fixes (P0) - DAY 1

### Fix P0-001: DailyUsage Table Name Mismatch

**Time**: 30 minutes
**Risk**: LOW (simple Meta change, no data migration)
**Blocking**: YES - must fix before any deployment

#### Step 1.1: Code Fix

**File**: `backend/apps/billing/usage.py`
**Location**: Line 163-171

**Current Code**:
```python
class DailyUsage(models.Model):
    ...
    class Meta:
        verbose_name = "Ежедневное использование"
        verbose_name_plural = "Ежедневное использование"
        unique_together = [["user", "date"]]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["-date"]),
        ]
```

**Fixed Code**:
```python
class DailyUsage(models.Model):
    ...
    class Meta:
        verbose_name = "Ежедневное использование"
        verbose_name_plural = "Ежедневное использование"
        db_table = "daily_usage"  # ← ADD THIS LINE
        unique_together = [["user", "date"]]
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["-date"]),
        ]
```

**Command**:
```bash
# Edit the file (use your preferred editor)
nano backend/apps/billing/usage.py

# Or via command line:
sed -i '/class Meta:/a\        db_table = "daily_usage"' backend/apps/billing/usage.py
```

#### Step 1.2: Create Migration

**Location**: Run on server or locally

```bash
cd /opt/EatFit24  # or your local path
docker compose exec backend python manage.py makemigrations billing telegram
```

**Expected Output**:
```
Migrations for 'billing':
  backend/apps/billing/migrations/0013_alter_dailyusage_options.py
    - Alter options for dailyusage
```

**Verify Migration**:
```bash
docker compose exec backend python manage.py sqlmigrate billing 0013
```

Should show SQL like:
```sql
ALTER TABLE "billing_dailyusage" RENAME TO "daily_usage";
```

Or simply a Meta update (no SQL if table doesn't exist yet).

#### Step 1.3: Apply Migration

```bash
docker compose exec backend python manage.py migrate
```

**Expected Output**:
```
Operations to perform:
  Apply all migrations: ...
Running migrations:
  Applying billing.0013_alter_dailyusage_options... OK
```

#### Step 1.4: Restart Services

```bash
docker compose restart backend celery-worker
```

**Wait for health**:
```bash
docker compose ps | grep healthy
# All services should show "healthy" status
```

#### Step 1.5: Verification Tests

**Test 1: Model Access**
```bash
docker compose exec -T backend python manage.py shell <<EOF
from apps.billing.usage import DailyUsage
from apps.users.models import User

# Should not crash
user = User.objects.first()
usage = DailyUsage.objects.get_today(user)
print(f"✅ SUCCESS: Created usage record for user {user.id}")
print(f"   photo_ai_requests: {usage.photo_ai_requests}")
EOF
```

**Expected Output**:
```
✅ SUCCESS: Created usage record for user X
   photo_ai_requests: 0
```

**Test 2: API Endpoint** (if auth configured):
```bash
# This will still fail due to auth, but error should be different now
curl -s http://localhost:8000/api/v1/billing/me/ | grep -E "UNAUTHORIZED|photo_ai_requests"
```

Should see "UNAUTHORIZED" (auth issue), NOT "ProgrammingError".

**Test 3: Usage Increment**
```bash
docker compose exec -T backend python manage.py shell <<EOF
from apps.billing.usage import DailyUsage
from apps.users.models import User

user = User.objects.first()

# Increment usage
DailyUsage.objects.increment_photo_ai_requests(user, amount=1)

# Verify
usage = DailyUsage.objects.get_today(user)
print(f"✅ Usage incremented: {usage.photo_ai_requests}")
assert usage.photo_ai_requests == 1, "Increment failed!"
EOF
```

**Test 4: Limit Check**
```bash
docker compose exec -T backend python manage.py shell <<EOF
from apps.billing.usage import check_and_increment_photo_ai_usage
from apps.users.models import User

user = User.objects.first()

# Should pass (FREE plan has limit of 3)
allowed, message = check_and_increment_photo_ai_usage(user)
print(f"Allowed: {allowed}, Message: {message}")
assert allowed == True
EOF
```

**Success Criteria**:
- ✅ No ProgrammingError
- ✅ DailyUsage records created
- ✅ Usage increments work
- ✅ Limit checks function

**If Tests Fail**:
1. Check table exists: `docker compose exec db psql -U eatfit24 -d eatfit24 -c "\d daily_usage"`
2. Check migrations: `docker compose exec backend python manage.py showmigrations billing`
3. Check logs: `docker compose logs backend | tail -50`

---

## PHASE 2: High Priority Fixes (P2) - DAY 1-2

### Fix P2-001: TELEGRAM_BOT_API_SECRET

**Time**: 5 minutes
**Risk**: NONE
**Blocking**: NO (but recommended before launch)

#### Step 2.1: Get Bot Secret

1. Contact bot owner or check Telegram BotFather
2. Secret should be in format: `abc123def456...`

#### Step 2.2: Update .env

**File**: `/opt/EatFit24/.env`

```bash
# SSH to server
ssh root@eatfit24.ru

# Edit .env
nano /opt/EatFit24/.env

# Add line:
TELEGRAM_BOT_API_SECRET=your_actual_secret_here
```

#### Step 2.3: Restart Bot Service

```bash
cd /opt/EatFit24
docker compose restart bot
```

#### Step 2.4: Verify

```bash
docker compose logs bot | grep "API_SECRET"
# Should NOT show "variable is not set" warning
```

---

### Fix P2-002: Redact Webhook Payload

**Time**: 30 minutes
**Risk**: LOW (pure addition, doesn't break existing)
**Blocking**: NO (can be post-launch)

#### Step 2.2.1: Add Redaction Function

**File**: `backend/apps/billing/webhooks/views.py`
**Location**: After imports, before yookassa_webhook function

```python
def _redact_sensitive_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redact sensitive data from webhook payload before database storage.

    Keeps event structure intact but removes:
    - Full payment_method details (keep only ID and type)
    - Recipient info (if present)
    - Any other PII
    """
    import copy
    safe_payload = copy.deepcopy(payload)

    if "object" in safe_payload and isinstance(safe_payload["object"], dict):
        obj = safe_payload["object"]

        # Redact payment_method (keep type, mask rest)
        if "payment_method" in obj and isinstance(obj["payment_method"], dict):
            pm = obj["payment_method"]
            obj["payment_method"] = {
                "id": "***REDACTED***",
                "type": pm.get("type", "unknown"),
                "saved": pm.get("saved", False),
            }

        # Redact recipient
        if "recipient" in obj:
            obj["recipient"] = "***REDACTED***"

        # Redact card details if present at top level
        if "card" in obj:
            obj["card"] = "***REDACTED***"

    return safe_payload
```

#### Step 2.2.2: Apply Redaction

**File**: Same file, find line ~113:

**Current**:
```python
webhook_log, created = WebhookLog.objects.select_for_update().get_or_create(
    event_id=event_id,
    defaults={
        "event_type": event_type,
        "payment_id": _extract_payment_id(payload),
        "status": "RECEIVED",
        "raw_payload": payload,  # ← CHANGE THIS
        "client_ip": client_ip,
    }
)
```

**Updated**:
```python
webhook_log, created = WebhookLog.objects.select_for_update().get_or_create(
    event_id=event_id,
    defaults={
        "event_type": event_type,
        "payment_id": _extract_payment_id(payload),
        "status": "RECEIVED",
        "raw_payload": _redact_sensitive_payload(payload),  # ← REDACTED
        "client_ip": client_ip,
    }
)
```

#### Step 2.2.3: Test

```bash
# Create test webhook log
docker compose exec -T backend python manage.py shell <<EOF
from apps.billing.models import WebhookLog

# Example payload with sensitive data
test_payload = {
    "event": "payment.succeeded",
    "object": {
        "id": "test_123",
        "payment_method": {
            "id": "pm_abc123",
            "type": "bank_card",
            "card": {
                "last4": "4242",
                "brand": "visa"
            }
        }
    }
}

# Import redaction function
from apps.billing.webhooks.views import _redact_sensitive_payload
redacted = _redact_sensitive_payload(test_payload)

print("Original:", test_payload)
print("Redacted:", redacted)

# Verify card details removed
assert "last4" not in str(redacted), "Card data not redacted!"
print("✅ Redaction works")
EOF
```

#### Step 2.2.4: Deploy

```bash
docker compose restart backend
```

**Note**: Existing webhook logs will keep old data. Only NEW webhooks will be redacted.

---

### Fix P2-003: Apply Pending Migrations

**Time**: 10 minutes
**Risk**: LOW (likely covered by P0-001 migration)
**Blocking**: PARTIAL (check after P0-001)

#### Step 2.3.1: Check for Pending

```bash
docker compose exec backend python manage.py makemigrations --dry-run billing telegram
```

**If Output Shows "No changes detected"**:
✅ Skip this step (covered by P0-001)

**If Output Shows Migrations**:
```bash
docker compose exec backend python manage.py makemigrations billing telegram
docker compose exec backend python manage.py migrate
docker compose restart backend
```

#### Step 2.3.2: Verify

```bash
docker compose logs backend | grep "changes that are not" | wc -l
# Should output: 0
```

---

## PHASE 3: Low Priority Fixes (P3) - POST-LAUNCH

### Fix P3-001: Clean Up Legacy Config Vars

**Time**: 10 minutes
**Risk**: NONE (removing unused vars)
**Blocking**: NO

#### Step 3.1.1: Backup Current .env

```bash
ssh root@eatfit24.ru
cd /opt/EatFit24
cp .env .env.backup_$(date +%Y%m%d_%H%M%S)
```

#### Step 3.1.2: Remove Legacy Vars

Edit `/opt/EatFit24/.env`:

**Remove these lines**:
```env
# DELETE:
YOOKASSA_SHOP_ID=1201077
YOOKASSA_SECRET_KEY=***
```

**Keep these**:
```env
YOOKASSA_SHOP_ID_TEST=1201077
YOOKASSA_API_KEY_TEST=***
YOOKASSA_SHOP_ID_PROD=1195531
YOOKASSA_API_KEY_PROD=***
YOOKASSA_MODE=prod
```

#### Step 3.1.3: Restart & Verify

```bash
docker compose restart backend
docker compose logs backend | grep YOOKASSA | head -5
# Should see initialization logs with correct shop_id
```

---

### Fix P3-002: Update Cache KEY_PREFIX

**Time**: 15 minutes
**Risk**: LOW (will invalidate existing cache entries)
**Blocking**: NO

#### Step 3.2.1: Update Settings

**File**: `backend/config/settings/production.py` (or wherever CACHES is defined)

**Find**:
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
        'KEY_PREFIX': 'foodmind',  # ← CHANGE THIS
        'TIMEOUT': 300,
    }
}
```

**Change to**:
```python
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://redis:6379/1',
        'KEY_PREFIX': 'eatfit24',  # ← NEW VALUE
        'TIMEOUT': 300,
    }
}
```

#### Step 3.2.2: Deploy & Flush Cache

```bash
docker compose restart backend celery-worker

# Optional: flush Redis cache to remove old keys
docker compose exec redis redis-cli FLUSHDB
```

**Warning**: Flushing cache will reset all throttle counters. Do this during low traffic.

---

### Fix P3-003: Fix User Without Subscription

**Time**: 5 minutes
**Risk**: NONE
**Blocking**: NO

```bash
docker compose exec -T backend python manage.py shell <<EOF
from apps.users.models import User
from apps.billing.views import _get_or_create_user_subscription

# Find users without subscription
users_without_sub = User.objects.filter(subscription__isnull=True)
print(f"Found {users_without_sub.count()} users without subscription")

for user in users_without_sub:
    sub = _get_or_create_user_subscription(user)
    print(f"✅ Created subscription for {user.username}: {sub.plan.code}")
EOF
```

---

## PHASE 4: Integration Testing - DAY 2

### Test Suite After All Fixes

**Time**: 1-2 hours
**Location**: Staging environment (or production with test data)

#### Test 4.1: Usage Tracking End-to-End

```bash
# Test user with FREE plan
docker compose exec -T backend python manage.py shell <<EOF
from apps.billing.usage import check_and_increment_photo_ai_usage
from apps.users.models import User
from apps.billing.models import Subscription

# Get FREE user
user = User.objects.filter(subscription__plan__code='FREE').first()
if not user:
    print("❌ No FREE user found")
    exit(1)

print(f"Testing user: {user.username}")
print(f"Plan: {user.subscription.plan.code}")
print(f"Daily limit: {user.subscription.plan.daily_photo_limit}")

# Test increment 3 times (should pass)
for i in range(3):
    allowed, msg = check_and_increment_photo_ai_usage(user)
    print(f"Request {i+1}: allowed={allowed}, msg={msg}")
    assert allowed, f"Request {i+1} should be allowed"

# 4th request should fail (limit=3)
allowed, msg = check_and_increment_photo_ai_usage(user)
print(f"Request 4: allowed={allowed}, msg={msg}")
assert not allowed, "Request 4 should be DENIED (limit exceeded)"
print("✅ Usage limits working correctly")
EOF
```

#### Test 4.2: Test Payment Creation (via Telegram Mini App)

**Prerequisites**: Telegram Mini App or test harness

```bash
# This requires Telegram Mini App context
# Steps:
# 1. Open EatFit24 bot in Telegram
# 2. Navigate to subscription/payment screen
# 3. Select PRO_MONTHLY plan
# 4. Click "Pay"
# 5. Verify confirmation_url received
# 6. Check backend logs

docker compose logs backend | grep "create-payment" | tail -20
```

**Expected in logs**:
```
Creating payment for user X, plan PRO_MONTHLY
YooKassa payment created: <payment_id>
Confirmation URL: https://yoomoney.ru/...
```

#### Test 4.3: Webhook Processing

**Option A: Wait for real payment**
1. Complete payment from Test 4.2
2. YooKassa sends webhook
3. Check logs

**Option B: Simulate webhook (dev only)**
```bash
# Get YooKassa IP for testing (won't work from external IP)
curl -X POST http://localhost:8000/api/v1/billing/webhooks/yookassa \
     -H "Content-Type: application/json" \
     -d '{
       "type": "notification",
       "event": "payment.succeeded",
       "object": {
         "id": "test_payment_123",
         "status": "succeeded",
         "amount": {"value": "299.00", "currency": "RUB"}
       }
     }'
```

**Check webhook log**:
```bash
docker compose exec -T backend python manage.py shell <<EOF
from apps.billing.models import WebhookLog
logs = WebhookLog.objects.order_by('-created_at')[:5]
for log in logs:
    print(f"{log.event_type}: {log.status} (event_id={log.event_id})")
EOF
```

#### Test 4.4: Throttling

```bash
# Test payment creation throttle (20/hour)
for i in {1..25}; do
  echo "Request $i:"
  curl -s -o /dev/null -w "%{http_code}\n" \
       -X POST http://localhost:8000/api/v1/billing/create-payment/ \
       -H "X-Telegram-Id: 123456789" \
       -H "Content-Type: application/json" \
       -d '{"plan_code": "PRO_MONTHLY"}'
  sleep 0.5
done | tee throttle_test.log

# Count 429 responses
grep "429" throttle_test.log | wc -l
# Should be > 0 (requests after 20th should be throttled)
```

---

## PHASE 5: Production Deployment - DAY 3

### Pre-Deployment Checklist

- [ ] P0-001 fixed and tested ✅
- [ ] P2-001 fixed (bot secret) ✅
- [ ] P2-003 applied (migrations) ✅
- [ ] All tests pass (Phase 4) ✅
- [ ] Staging tests successful ✅
- [ ] Backup current production database
- [ ] Rollback plan documented
- [ ] On-call team notified
- [ ] Monitoring configured

### Deployment Steps

#### Step 5.1: Backup Production Database

```bash
ssh root@eatfit24.ru
cd /opt/EatFit24

# Backup database
docker compose exec db pg_dump -U eatfit24 -d eatfit24 > backup_pre_billing_fix_$(date +%Y%m%d_%H%M%S).sql

# Backup .env
cp .env .env.backup_pre_billing_fix_$(date +%Y%m%d_%H%M%S)
```

#### Step 5.2: Pull Latest Code

```bash
cd /opt/EatFit24
git stash  # If local changes
git pull origin main  # Or your deployment branch
```

#### Step 5.3: Apply Migrations

```bash
docker compose exec backend python manage.py migrate --plan
# Review migration plan

docker compose exec backend python manage.py migrate
```

#### Step 5.4: Restart Services

```bash
docker compose restart backend celery-worker
docker compose ps  # Verify all healthy
```

#### Step 5.5: Smoke Test Production

```bash
# Test public endpoint
curl -s https://eatfit24.ru/api/v1/billing/plans/ | jq '.[0].code'
# Should output: "FREE"

# Check logs for errors
docker compose logs backend --tail=50 | grep -i error
```

#### Step 5.6: Monitor First Hour

```bash
# Watch logs in real-time
docker compose logs -f backend | grep -E "billing|payment|webhook"

# Check error rate every 5 minutes
watch -n 300 'docker compose logs backend --since 5m | grep -i error | wc -l'
```

---

## ROLLBACK PLAN

If critical issues detected after deployment:

### Rollback Step 1: Stop Processing

```bash
docker compose stop backend celery-worker
```

### Rollback Step 2: Restore Previous Code

```bash
cd /opt/EatFit24
git log --oneline -5  # Find commit before deployment
git reset --hard <previous_commit_hash>
```

### Rollback Step 3: Restore Database

```bash
# Only if database was corrupted
docker compose exec -T db psql -U eatfit24 -d eatfit24 < backup_pre_billing_fix_*.sql
```

### Rollback Step 4: Restore .env

```bash
cp .env.backup_pre_billing_fix_* .env
```

### Rollback Step 5: Restart

```bash
docker compose up -d backend celery-worker
docker compose ps  # Verify healthy
```

---

## Post-Deployment Monitoring (Week 1)

### Metrics to Watch

1. **Payment Success Rate**:
   ```bash
   docker compose exec -T backend python manage.py shell <<EOF
   from apps.billing.models import Payment
   total = Payment.objects.count()
   succeeded = Payment.objects.filter(status='SUCCEEDED').count()
   print(f"Success rate: {succeeded}/{total} = {succeeded/total*100:.1f}%")
   EOF
   ```

2. **Webhook Processing**:
   ```bash
   docker compose exec -T backend python manage.py shell <<EOF
   from apps.billing.models import WebhookLog
   from django.db.models import Count
   WebhookLog.objects.values('status').annotate(count=Count('id'))
   EOF
   ```

3. **Usage Tracking**:
   ```bash
   docker compose exec -T backend python manage.py shell <<EOF
   from apps.billing.usage import DailyUsage
   today_usage = DailyUsage.objects.filter(date=timezone.now().date()).count()
   print(f"Users tracked today: {today_usage}")
   EOF
   ```

4. **Error Rate**:
   ```bash
   docker compose logs backend --since 24h | grep -i error | wc -l
   ```

### Alerting Rules (Recommended)

- Payment failure rate > 5%
- Webhook FAILED status > 2%
- Database errors > 10/hour
- API 5xx errors > 20/hour

---

## Summary

**Total Estimated Time**: 4-6 hours (spread across 2-3 days)

**Risk Assessment**:
- P0 fix: LOW risk (simple Meta change)
- P2 fixes: LOW risk (additions, no breaking changes)
- P3 fixes: VERY LOW risk (cosmetic improvements)

**Success Criteria**:
- ✅ No ProgrammingError when accessing DailyUsage
- ✅ Usage limits enforced for FREE users
- ✅ Payment creation works end-to-end
- ✅ Webhooks processed and subscriptions extended
- ✅ No critical errors in first 24 hours

**Next Review**: 7 days after deployment
**Owner**: DevOps/Backend team
**Contact**: Check BUG-REPORT.md for details

---

**Plan Version**: 1.0
**Last Updated**: 2025-12-17
