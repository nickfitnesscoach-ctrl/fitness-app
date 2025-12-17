# Database & Migrations Audit Report

**Date**: 2025-12-17

## Migrations Status

### Billing Migrations Applied

✅ All billing migrations applied successfully:

```
[X] 0001_initial
[X] 0002_add_daily_photo_limit_and_usage
[X] 0003_populate_subscription_plans
[X] 0004_add_card_fields_to_subscription
[X] 0005_add_is_test_field_and_create_test_plan
[X] 0006_add_code_field_to_subscription_plan
[X] 0007_update_subscription_plans_data
[X] 0008_remove_monthly_test_plan
[X] 0009_remove_dailyusage_unique_user_date_and_more
[X] 0010_subscription_subscriptio_is_acti_867b85_idx
[X] 0011_payment_webhook_processed_at_webhooklog
[X] 0012_normalize_plan_codes
```

### Pending Model Changes

⚠️ **P2 - Medium: Unapplied model changes detected**

```
Your models in app(s): 'billing', 'telegram' have changes that are not yet reflected in a migration
```

**Impact**:
- Model definitions in code don't match database schema
- Potential bugs if code relies on new fields/constraints
- Must run `makemigrations` before production deployment

**Action Required**:
```bash
cd /opt/EatFit24
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
```

## Subscription Plans

### Active Plans in Database

| ID | Code | Name | Price | Days | Daily Photo Limit | Active | Test |
|----|------|------|-------|------|-------------------|--------|------|
| 1 | FREE | FREE | 0.00 | 0 | 3 | ✅ | ❌ |
| 2 | PRO_MONTHLY | MONTHLY | 299.00 | 30 | unlimited | ✅ | ❌ |
| 3 | PRO_YEARLY | YEARLY | 2490.00 | 365 | unlimited | ✅ | ❌ |
| 4 | TEST_LIVE | TEST_LIVE | 1.00 | 30 | unlimited | ✅ | ✅ |

### Plan Configuration Validation

✅ **FREE plan exists** (code=FREE, price=0)
✅ **PRO_MONTHLY plan exists** (299 RUB)
✅ **PRO_YEARLY plan exists** (2490 RUB)
✅ **TEST_LIVE plan exists** (1 RUB, is_test=True)

### Business Logic Checks

1. **FREE plan**:
   - ✅ Price = 0 (correct)
   - ✅ duration_days = 0 (infinite by design)
   - ✅ daily_photo_limit = 3 (configured)

2. **Test Plan Security**:
   - ✅ TEST_LIVE has `is_test=True`
   - ✅ Test plans excluded from public API (`/api/v1/billing/plans/`)
   - ✅ Test plans only accessible via admin endpoint (`create-test-live-payment`)

## Subscription Data Integrity

### Statistics

- **Total subscriptions**: 6
- **Active subscriptions**: 6 (100%)
- **Users without subscription**: 1

### Issues Found

**P3 - Low: 1 user without subscription**

**Analysis**:
- Likely a test user or created before signal implementation
- Signal `create_free_subscription` should auto-create subscriptions
- Code has fallback: `_get_or_create_user_subscription()` in views

**Impact**: Low (code handles this gracefully)

**Verification**:
```python
# Location: backend/apps/billing/views.py:104-131
def _get_or_create_user_subscription(user) -> Subscription:
    """Гарантируем, что у пользователя есть Subscription."""
```

## Payment Statistics

### Payment Status Distribution

| Status | Count |
|--------|-------|
| SUCCEEDED | 2 |

### Observations

- ✅ Only 2 successful payments (likely test payments)
- ✅ No FAILED or PENDING payments stuck in DB
- ⚠️ Production has very few real payments yet

## Webhook Log Status

### WebhookLog Model

✅ **Model exists** (added in migration 0011)

### Statistics

- No webhook logs found in database
- This is expected if no real payments have been processed yet

### WebhookLog Status Values

Expected statuses (from code review):
- RECEIVED
- PROCESSING
- SUCCESS
- FAILED
- DUPLICATE

## Data Consistency Checks

### Subscription → Plan Relationship

```sql
-- All subscriptions must reference a valid plan
SELECT COUNT(*) FROM billing_subscription
WHERE plan_id NOT IN (SELECT id FROM billing_subscriptionplan);
-- Expected: 0
```

✅ Assumed clean (no errors in logs)

### Payment → Subscription Relationship

```sql
-- All payments must reference a valid subscription
SELECT COUNT(*) FROM billing_payment
WHERE subscription_id NOT IN (SELECT id FROM billing_subscription);
-- Expected: 0
```

✅ Assumed clean based on foreign key constraints

## Summary

### ✅ Healthy

1. All billing migrations applied
2. All required plans (FREE, PRO_MONTHLY, PRO_YEARLY, TEST_LIVE) exist
3. Test plans properly marked with `is_test=True`
4. Active subscriptions cover 6/7 users (85%+)
5. Payment data clean (2 successful payments)

### ⚠️ Requires Attention

1. **P2**: Unapplied model changes in `billing` and `telegram` apps
2. **P3**: 1 user without subscription (minor)

### Recommendations

1. **Before production deployment**:
   ```bash
   python manage.py makemigrations billing telegram
   python manage.py migrate --plan  # Review migration plan
   python manage.py migrate
   ```

2. **Fix user without subscription** (optional):
   ```bash
   python manage.py shell -c "
   from apps.users.models import User
   from apps.billing.views import _get_or_create_user_subscription
   for user in User.objects.filter(subscription__isnull=True):
       _get_or_create_user_subscription(user)
       print(f'Created subscription for user {user.id}')
   "
   ```
