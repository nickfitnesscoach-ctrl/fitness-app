# Billing SSOT — EatFit24

> **Status:** ACTIVE
> **Target:** Developers, DevOps, Support
> **Domain:** Subscriptions, Payments, YooKassa Integration

---

## 1. Core Principles

| Principle | Description |
|-----------|-------------|
| **Webhook = Source of Truth** | A payment is only considered successful after a validated `payment.succeeded` webhook. |
| **Server-Side Pricing** | Prices are always fetched from the database (`SubscriptionPlan`). Never trust prices sent from the client. |
| **Atomic Throttling** | Daily usage limits are handled atomically to prevent race conditions during photo analysis. |
| **YooKassaService Isolation** | All external payment gateway calls must go through `billing.services.YooKassaService`. |

---

## 2. System Architecture

The billing system is designed with a **webhook-first** approach to ensure reliability and handle asynchronous payment confirmations.

### Component Map
```
billing/
├── models.py          # SubscriptionPlan, Subscription, Payment, Refund, WebhookLog
├── views.py           # API endpoints
├── services.py        # YooKassaService + Business Logic
├── notifications.py   # Admin Telegram Alerts
├── usage.py           # Atomic Daily Limit Tracking
├── webhooks/          # YooKassa Webhook Entry Point
│   ├── views.py       # IP Validation & Redaction
│   ├── handlers.py    # Success/Cancel Business Logic
│   └── tasks.py       # Async Celery Processing (queue: billing)
└── management/        # Scheduled Jobs (Recurring, Cleanup)
```

### Payment Flow
1. **Frontend** calls `POST /billing/create-payment/`.
2. **Backend** validates `plan_code`, calculates price from DB, creates `Payment(status=PENDING)`.
3. **YooKassa API** creates payment and returns `confirmation_url`.
4. **User** completes payment. YooKassa redirects user to `return_url` (status is still unconfirmed).
5. **YooKassa Webhook** sends `payment.succeeded`.
6. **Backend Webhook View** validates IP, logs raw payload, and enqueues **Celery Task**.
7. **Celery Task** calls `activate_or_extend_subscription()`, updates `Payment`, and alerts admins.

---

## 3. Data Models

### Key Objects
- **`SubscriptionPlan`**: The templates (`FREE`, `PRO_MONTHLY`, `PRO_YEARLY`). Defines price, duration, and photo limits.
- **`Subscription`**: 1:1 with User. Tracks active status, expiration (`end_date`), and saved payment methods.
- **`Payment`**: Tracks every transaction attempt. Statuses: `PENDING`, `SUCCEEDED`, `CANCELED`, `FAILED`, `REFUNDED`.
- **`WebhookLog`**: Audit trail of every payload received from YooKassa.

### Subscription Status Matrix
| Current State | Event | New State | Handled By |
|---------------|-------|-----------|------------|
| FREE (Active) | payment.succeeded | PRO (Active) | `handlers.py` |
| PRO (Active) | payment.succeeded | PRO (Extended) | `handlers.py` |
| PRO (Active) | `end_date` passed | PRO (Expired) | `cleanup_expired_subscriptions` |
| PRO (Expired) | Cleanup Job | FREE | `cleanup_expired_subscriptions` |

---

## 4. Recurring Subscriptions (Auto-Renew)

Implemented on **2026-01-08**. Allows automatic billing before subscription expiry.

### Mechanics
1. **Enrollment**: When a user pays for PRO with `save_payment_method=true`, YooKassa returns a `payment_method.id`.
2. **Persistence**: The ID is saved in `Subscription.yookassa_payment_method_id` and `auto_renew` is set to `True`.
3. **Trigger**: `process_due_renewals` (Celery Beat) runs hourly.
4. **Window**: Finds active subscriptions expiring within the next **24 hours** without a pending renewal payment.
5. **Charge**: Initiates a recurring charge through YooKassa using the saved `payment_method_id`.
6. **Confirmation**: Handled via the same webhook flow as manual payments.

### Cancellation Logic (`payment.canceled`)
| Reason | Action |
|--------|--------|
| `permission_revoked`, `card_expired` | Set `auto_renew = False`, clear payment method. |
| `insufficient_funds`, `3d_secure_failed` | Keep `auto_renew = True`. Allow retry in next hourly run. |

---

## 5. Security & Isolation

### Webhook Protection
- **IP Allowlist**: Only accepts requests from official YooKassa CIDR blocks.
- **XFF Trust Guard**: Only trusts `X-Forwarded-For` if the immediate proxy is in `WEBHOOK_TRUSTED_PROXIES`.
- **Idempotency**: 
  - **Level 1**: Database `unique` constraint on `provider_event_id`.
  - **Level 2**: `Payment.status` checks in business logic.
- **Payload Redaction**: Views redact sensitive card details before logging `raw_payload`.

---

## 6. Observability

### Trace IDs
Every webhook is assigned a short `trace_id` (e.g., `[abc12345]`). This ID is propagated through Celery tasks and logs to allow full request correlation.

### Essential Commands
- **Logs**: `docker logs -f eatfit24-celery-worker | grep "[BILLING]"`
- **Stuck Payments**: `SELECT id, status FROM payments WHERE status='PENDING' AND created_at < NOW() - INTERVAL '1 hour';`

---

## 7. Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `YOOKASSA_SHOP_ID` | Yes | Commercial ID from YooKassa Dashboard |
| `YOOKASSA_SECRET_KEY` | Yes | API Secret (NEVER commit to repo) |
| `BILLING_RECURRING_ENABLED` | No | Boolean. Enables card saving and auto-renew loop. |
| `WEBHOOK_TRUST_XFF` | No | Boolean. Enable for production setups behind Nginx. |

---

## 8. Operational Runbook

### Handling Failed Payments
If a user reports a "successful" payment that didn't activate PRO:
1. Search `WebhookLog` by `user_id` or date.
2. Check `trace_id` in logs.
3. Verify if the Celery task crashed or is still processing.

### Manual Subscription Fix
```python
# python manage.py shell
from apps.billing.models import Subscription, SubscriptionPlan
from django.contrib.auth import get_user_model

user = get_user_model().objects.get(username='...')
plan = SubscriptionPlan.objects.get(code='PRO_YEARLY')
sub = user.subscription
sub.plan = plan
sub.activate_or_extend(days=365)
sub.save()
```
