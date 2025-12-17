# Security Audit Report: billing/

> **Date:** 2024-12-17  
> **Scope:** `backend/apps/billing/*` (views, webhooks, services, models, management commands)  
> **Auditor:** Automated Security Review  

---

## Executive Summary

**Overall Risk Level: MEDIUM**

The billing module is well-architected with strong security foundations:
- ✅ IP allowlist for webhook protection
- ✅ Idempotency via `WebhookLog` + `select_for_update()`
- ✅ Price/plan_code taken exclusively from DB (not frontend)
- ✅ Atomic transactions in payment & subscription handlers
- ✅ `F()` expressions for race-safe usage counter increments
- ✅ Throttle classes defined for payment creation and webhooks

**Key Issues Found:**
- 🔴 1 Critical: Throttles defined but NOT applied to billing views
- 🟡 2 High: XFF spoofing risk, limit check race condition
- 🟠 3 Medium: Duplicate YooKassa clients, missing return_url validation, test plan exposure
- 🔵 4 Low: Logging improvements, dead code, test coverage gaps

---

## Must Fix (Critical)

### [CRITICAL-001] Throttles Defined But Not Applied to Billing Views

**Where:** [views.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/views.py), [throttles.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/throttles.py)

**Risk:** An attacker can spam `/create-payment/` and flood the database with PENDING Payment records, potentially causing:
- Database bloat / DoS
- YooKassa API rate limit exhaustion
- Financial reconciliation headaches

**Evidence:**  
`throttles.py` defines `PaymentCreationThrottle` (20/hour) and `WebhookThrottle` (100/hour), but they are **never imported or applied** to any view in `views.py`.

**How to Reproduce:**
```bash
# Loop 50 requests in under a minute — all will succeed
for i in {1..50}; do
  curl -X POST /api/v1/billing/create-payment/ \
    -H "Authorization: Bearer <token>" \
    -d '{"plan_code": "PRO_MONTHLY"}'
done
```

**Fix:**
```python
# views.py - Add to create_payment and similar endpoints
from .throttles import PaymentCreationThrottle

@api_view(["POST"])
@permission_classes([IsAuthenticated])
@throttle_classes([PaymentCreationThrottle])  # ADD THIS LINE
def create_payment(request):
    ...
```

Also apply `WebhookThrottle` to the webhook view in `webhooks/views.py` (convert to class-based or use decorator).

---

## Should Fix (High/Medium)

### [HIGH-001] X-Forwarded-For Spoofing Risk (Webhook IP Check)

**Where:** [webhooks/views.py#L144-154](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/webhooks/views.py#L144-L154), [webhooks/utils.py#L75-91](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/webhooks/utils.py#L75-L91)

**Risk:** If the server is exposed directly to the internet (no trusted reverse proxy), an attacker can spoof `X-Forwarded-For` header to bypass the YooKassa IP allowlist and send fake webhooks.

**Current Code:**
```python
def _get_client_ip(request: HttpRequest) -> str | None:
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()  # Takes first, trusts it blindly
    return request.META.get("REMOTE_ADDR")
```

**Attack Scenario:**
```bash
curl -X POST /api/v1/billing/webhooks/yookassa \
  -H "X-Forwarded-For: 185.71.76.10" \  # Spoofed YooKassa IP
  -d '{"event": "payment.succeeded", "object": {...}}'
```

**Fix Options:**

1. **If behind Nginx/Cloudflare:** Configure Django to trust only the first proxy's IP:
   ```python
   # settings.py
   USE_X_FORWARDED_HOST = True
   SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
   
   # Use django-xff or similar for proper XFF parsing
   ```

2. **Alternative — Always use REMOTE_ADDR in production:**
   ```python
   def _get_client_ip(request: HttpRequest) -> str | None:
       # In production with trusted proxy, proxy sets REMOTE_ADDR correctly
       if settings.DEBUG:
           xff = request.META.get("HTTP_X_FORWARDED_FOR")
           if xff:
               return xff.split(",")[0].strip()
       return request.META.get("REMOTE_ADDR")
   ```

3. **Add webhook signature validation** (YooKassa supports HMAC — recommended as defense-in-depth).

---

### [HIGH-002] Race Condition in Daily Limit Check (AI Recognition)

**Where:** [ai/views.py#L195-213](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/ai/views.py#L195-L213)

**Risk:** User sends 10 simultaneous requests. All 10 read `usage.photo_ai_requests = 2` (limit = 3). All 10 pass the check. All 10 increment. User gets 12 AI requests instead of 3.

**Current Code (NOT in billing/ but related):**
```python
usage = DailyUsage.objects.get_today(request.user)  # No lock

if plan.daily_photo_limit is not None and usage.photo_ai_requests >= plan.daily_photo_limit:
    return 429 Error

# ... later in recognize_and_save_meal():
DailyUsage.objects.increment_photo_ai_requests(user)  # Has lock, but too late
```

**Fix:** Atomic check-and-increment pattern:
```python
# In ai/views.py or a dedicated service
from django.db import transaction

def check_and_increment_usage(user, plan) -> bool:
    """Returns True if allowed, False if limit exceeded."""
    if plan.daily_photo_limit is None:
        DailyUsage.objects.increment_photo_ai_requests(user)
        return True
    
    with transaction.atomic():
        usage = DailyUsage.objects.select_for_update().get_today(user)
        if usage.photo_ai_requests >= plan.daily_photo_limit:
            return False
        DailyUsage.objects.filter(pk=usage.pk).update(
            photo_ai_requests=F("photo_ai_requests") + 1
        )
        return True
```

> **Note:** This issue is in `ai/views.py`, not `billing/`, but directly relates to billing limits.

---

### [MEDIUM-001] Two Duplicate YooKassa Clients

**Where:** [services.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/services.py) (SDK), [yookassa_client.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/yookassa_client.py) (requests)

**Risk:**
- Logic drift between two implementations
- Double maintenance burden
- SDK uses global state (`Configuration.*`), requests-based client is isolated

**Current Usage:**
| Client | Used By |
|--------|---------|
| `YooKassaService` (SDK) | `views.py`, `services.py` (main payments) |
| `YooKassaClient` (requests) | Not currently imported anywhere visible |
| Direct requests in command | `process_recurring_payments.py` (3rd copy!) |

**Fix:** Consolidate to a single client. Recommend SDK wrapper in `services.py` since it's already in use:
1. Remove `yookassa_client.py` if unused
2. Replace direct `requests.post()` in `process_recurring_payments.py` with `YooKassaService.create_recurring_payment()`

---

### [MEDIUM-002] return_url Not Validated for Open Redirect

**Where:** [views.py#L492](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/views.py#L492)

**Risk:** Frontend can pass arbitrary `return_url`, which is sent to YooKassa and used for redirect after payment. Attacker could craft:
```
POST /create-payment/
{"plan_code": "PRO_MONTHLY", "return_url": "https://evil.com/phishing"}
```

User pays, gets redirected to attacker's phishing site.

**Current Code:**
```python
return_url = request.data.get("return_url") or _build_default_return_url(request)
```

**Fix:**
```python
def _validate_return_url(url: str) -> bool:
    from urllib.parse import urlparse
    allowed_domains = getattr(settings, 'ALLOWED_RETURN_URL_DOMAINS', ['eatfit24.com', 'localhost'])
    parsed = urlparse(url)
    return parsed.hostname in allowed_domains

# In create_payment:
return_url = request.data.get("return_url")
if return_url and not _validate_return_url(return_url):
    return_url = _build_default_return_url(request)
```

---

### [MEDIUM-003] Test Plan Potentially Accessible to Non-Admins

**Where:** [views.py#L586-668](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/views.py#L586-L668)

**Risk:** While `create_test_live_payment` checks admin status, the TEST_LIVE plan could be used via regular `/create-payment/` if it's `is_active=True` and not filtered.

**Evidence:** `get_subscription_plans()` filters `is_test=False`, but `create_payment()` uses `_get_plan_by_code_or_legacy()` which only checks `is_active=True`.

**Attack:**
```bash
curl -X POST /api/v1/billing/create-payment/ \
  -d '{"plan_code": "TEST_LIVE"}'
# If plan exists and is_active=True, payment is created for 1₽
```

**Fix:**
```python
# In _get_plan_by_code_or_legacy or create_payment validation:
plan = SubscriptionPlan.objects.get(code=plan_code, is_active=True)
if plan.is_test:
    raise ValueError("Test plans cannot be used for regular payments")
```

---

## Nice to Have (Low)

### [LOW-001] raw_payload May Contain Sensitive Data

**Where:** [models.py#L488](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/models.py#L488)

`WebhookLog.raw_payload` stores full webhook JSON. YooKassa webhooks may contain card data in `payment_method.card.*`. While masked, consider:
- Log rotation / retention policy
- Access restriction in Django Admin (already somewhat handled by admin permissions)

**Recommendation:** Add field-level audit logging or redact sensitive fields before storage.

---

### [LOW-002] Missing Event ID Uniqueness Constraint

**Where:** [models.py#L474](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/models.py#L474)

`WebhookLog.event_id` has `db_index=True` but no `unique=True`. While the code uses `get_or_create()` for idempotency, a DB-level unique constraint provides defense-in-depth.

**Fix:**
```python
event_id = models.CharField("ID события YooKassa", max_length=255, unique=True, db_index=True)
# Requires migration
```

---

### [LOW-003] Webhook Logs Error on `Payment.DoesNotExist`

**Where:** [webhooks/handlers.py#L89](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/billing/webhooks/handlers.py#L89)

If YooKassa sends a webhook for a payment that doesn't exist locally (edge case: payment created in YooKassa directly), the handler raises `Payment.DoesNotExist` which bubbles up as FAILED webhook.

**Current:** Exception logged, webhook marked FAILED.  
**Better:** Explicit handling with warning log, webhook marked "UNKNOWN_PAYMENT".

---

### [LOW-004] Celery Task Increments Usage After Potential Failure

**Where:** [ai/tasks.py](file:///d:/NICOLAS/1_PROJECTS/_IT_Projects/Fitness-app/backend/apps/ai/tasks.py) (not in billing but related)

Usage counter is incremented in task even if AI recognition fails. Consider incrementing only on success, or increment at request time (before processing).

---

## Quick Wins

| # | Fix | Effort | Impact |
|---|-----|--------|--------|
| 1 | Add `@throttle_classes([PaymentCreationThrottle])` to `create_payment`, `bind_card_start`, `subscribe` | 5 min | High |
| 2 | Add `is_test=False` check in `_get_plan_by_code_or_legacy()` | 5 min | Medium |
| 3 | Add `unique=True` to `WebhookLog.event_id` + migration | 10 min | Low |
| 4 | Add return_url domain whitelist validation | 15 min | Medium |
| 5 | Document XFF assumption in webhooks README | 5 min | N/A |
| 6 | Remove unused `yookassa_client.py` if confirmed not used | 5 min | Low |
| 7 | Add explicit `Payment.DoesNotExist` handling in webhook handlers | 10 min | Low |

---

## Regression Checklist

After applying fixes, verify:

- [ ] **Test payment creation:** User can create payment for PRO_MONTHLY, gets confirmation_url
- [ ] **Test throttling:** 21st request in 1 hour returns 429 Too Many Requests
- [ ] **Webhook acceptance:** POST from YooKassa IP returns 200
- [ ] **Webhook rejection:** POST from spoofed IP (if XFF fix applied) returns 403
- [ ] **Duplicate webhook:** Same event_id second time returns 200 (idempotent), subscription NOT extended twice
- [ ] **Auto-renewal:** `process_recurring_payments` command creates payment, webhook extends subscription
- [ ] **Daily limits:** FREE user blocked at photo 4, PRO user unlimited
- [ ] **Test plan blocked:** `/create-payment/ {"plan_code": "TEST_LIVE"}` returns 400 for non-admin
- [ ] **Return URL validation:** Malicious return_url falls back to default

---

## Assumptions & Limitations

1. **Trusted Proxy:** This audit assumes the server is behind Nginx/Cloudflare which strips client-provided XFF. If exposed directly, XFF spoofing is a critical issue.

2. **YooKassa Webhook Signature:** YooKassa supports HMAC signatures for webhooks. This module relies solely on IP allowlist. Consider adding signature validation for defense-in-depth.

3. **Out of Scope:** This audit did not cover:
   - Frontend security
   - Django Admin access controls (beyond defaults)
   - Infrastructure (Docker, Nginx config)
   - Other apps (`ai/`, `nutrition/`, etc.) except where directly related to billing limits

---

*Report generated by Security Audit - EatFit24 Billing Module*
