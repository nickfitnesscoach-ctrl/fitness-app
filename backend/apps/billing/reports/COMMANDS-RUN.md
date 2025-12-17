# Commands Executed During Audit

**Audit Date**: 2025-12-17
**Auditor**: Claude Code DevOps Audit
**Server**: eatfit24.ru
**Project Path**: /opt/EatFit24

This document lists all commands executed during the billing module audit for reproducibility.

---

## Environment Discovery

### Find Project Location
```bash
ssh root@eatfit24.ru "find /opt /root /home -maxdepth 3 -name 'docker-compose.yml' -o -name 'backend' -type d 2>/dev/null | head -20"
```

### Check Docker Services
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose ps"
```

### Get Container Logs
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose logs --tail=200 backend 2>&1 | tail -100"
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose logs --tail=200 db 2>&1 | tail -50"
```

### Check Python/Django Versions
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python --version"
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend pip list | grep -E 'Django|djangorestframework|yookassa'"
```

---

## Configuration Audit

### Check Environment Variables (Masked)
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && cat .env | grep -E 'YOOKASSA|CACHE|ALLOWED|REDIS' | sed 's/\\(API_KEY.*=\\)\\(.*\\)/\\1***MASKED***/; s/\\(SECRET.*=\\)\\(.*\\)/\\1***MASKED***/'"
```

### Check Django Settings
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python manage.py shell -c 'from django.conf import settings; print(\"YOOKASSA_MODE:\", settings.YOOKASSA_MODE); print(\"YOOKASSA_SHOP_ID:\", settings.YOOKASSA_SHOP_ID[:4] + \"***\" if settings.YOOKASSA_SHOP_ID else \"NOT SET\"); print(\"YOOKASSA_SECRET_KEY:\", \"***PRESENT***\" if settings.YOOKASSA_SECRET_KEY else \"NOT SET\"); print(\"YOOKASSA_RETURN_URL:\", settings.YOOKASSA_RETURN_URL)'"
```

### Check Cache Configuration
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python manage.py shell -c 'from django.conf import settings; import pprint; print(\"ALLOWED_RETURN_URL_DOMAINS:\", getattr(settings, \"ALLOWED_RETURN_URL_DOMAINS\", \"NOT DEFINED\")); print(\"\\nCACHES:\"); pprint.pprint(settings.CACHES)'"
```

### Check Authentication Classes
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python manage.py shell -c 'from django.conf import settings; import pprint; print(\"REST_FRAMEWORK authentication:\"); pprint.pprint(settings.REST_FRAMEWORK.get(\"DEFAULT_AUTHENTICATION_CLASSES\", []))'"
```

### Check Webhook Settings
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python manage.py shell -c 'from django.conf import settings; print(\"WEBHOOK_TRUST_XFF:\", getattr(settings, \"WEBHOOK_TRUST_XFF\", \"NOT SET (defaults to False)\"))'"
```

---

## Database Checks

### Check Migrations Status
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python manage.py showmigrations billing telegram"
```

### Check Subscription Plans
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python manage.py shell -c '
from apps.billing.models import SubscriptionPlan, Subscription
from apps.users.models import User

plans = SubscriptionPlan.objects.all().order_by(\"price\")
print(\"=== SUBSCRIPTION PLANS ===\")
for p in plans:
    print(f\"ID: {p.id}, Code: {p.code}, Name: {p.name}, Price: {p.price}, Days: {p.duration_days}, Active: {p.is_active}, Test: {p.is_test}\")

print(\"\\n=== USERS WITHOUT SUBSCRIPTION ===\")
users_without_sub = User.objects.filter(subscription__isnull=True).count()
print(f\"Count: {users_without_sub}\")

print(\"\\n=== SUBSCRIPTION STATS ===\")
total_subs = Subscription.objects.count()
active_subs = Subscription.objects.filter(is_active=True).count()
print(f\"Total subscriptions: {total_subs}\")
print(f\"Active subscriptions: {active_subs}\")
'"
```

### Check Payment Statistics
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python manage.py shell -c '
from apps.billing.models import Payment, WebhookLog
from django.db.models import Count

print(\"=== PAYMENT STATS ===\")
payments_by_status = Payment.objects.values(\"status\").annotate(count=Count(\"id\")).order_by(\"status\")
for stat in payments_by_status:
    print(f\"{stat[\"status\"]}: {stat[\"count\"]}\")

print(\"\\n=== WEBHOOK LOG STATS ===\")
try:
    webhook_by_status = WebhookLog.objects.values(\"status\").annotate(count=Count(\"id\")).order_by(\"status\")
    for stat in webhook_by_status:
        print(f\"{stat[\"status\"]}: {stat[\"count\"]}\")
except Exception as e:
    print(f\"Error: {e}\")
'"
```

---

## Code Inspection

### Search for Hardcoded Secrets
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && grep -r 'live_' backend/apps/billing/ || echo 'No hardcoded live_ keys found'"
ssh root@eatfit24.ru "cd /opt/EatFit24 && grep -r 'test_' backend/apps/billing/ | grep -v '.pyc' | grep -v 'is_test' | head -20"
```

### Find DailyUsage References
```bash
# Local command
grep -r "class DailyUsage" backend/apps/billing/ -A 20
grep -r "DailyUsage|dailyusage" backend/apps/billing/migrations/*.py
```

---

## API Testing

### Test Public Plans Endpoint
```bash
ssh root@eatfit24.ru 'curl -s http://localhost:8000/api/v1/billing/plans/ | head -c 500'
```

### Create Test User and JWT Token
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python manage.py shell -c '
from apps.users.models import User
from rest_framework_simplejwt.tokens import RefreshToken

user, created = User.objects.get_or_create(
    username=\"test_api_user\",
    defaults={\"email\": \"test@eatfit24.ru\", \"is_active\": True}
)
if created:
    user.set_password(\"test_password_123\")
    user.save()

refresh = RefreshToken.for_user(user)
print(str(refresh.access_token))
'"
```

### Test Authenticated Endpoints (Failed due to auth config)
```bash
ssh root@eatfit24.ru 'TOKEN="<jwt_token>"; curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/billing/me/'
```

### Test Internal Services
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python manage.py shell -c '
from apps.users.models import User
from apps.billing.models import Subscription
from apps.billing.services import get_effective_plan_for_user

user = User.objects.get(username=\"test_monthly\")
print(f\"Test User: {user.username} (ID: {user.id})\")

sub = Subscription.objects.get(user=user)
print(f\"Subscription Plan: {sub.plan.code}\")
print(f\"Active: {sub.is_active}\")
print(f\"End Date: {sub.end_date}\")

plan = get_effective_plan_for_user(user)
print(f\"Effective Plan: {plan.code}\")
print(f\"Daily Photo Limit: {plan.daily_photo_limit}\")
'"
```

### Test DailyUsage (This FAILED - P0 Bug Discovered)
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python manage.py shell -c '
from apps.billing.usage import DailyUsage
from apps.users.models import User

user = User.objects.first()
usage = DailyUsage.objects.get_today(user)  # ← FAILS HERE
print(f\"Today Photo Requests: {usage.photo_ai_requests}\")
'"
# Result: ProgrammingError: relation "billing_dailyusage" does not exist
```

---

## File Inspection

### List Project Structure
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && ls -la"
```

### Read Docker Compose File
```bash
# Local command (file already read)
cat docker-compose.yml
```

### Read Key Files
```bash
# Local commands executed via Read tool:
# - backend/apps/billing/services.py
# - backend/apps/billing/views.py
# - backend/apps/billing/throttles.py
# - backend/apps/billing/webhooks/views.py
# - backend/apps/billing/webhooks/handlers.py
# - backend/apps/billing/webhooks/utils.py
# - backend/apps/billing/models.py
# - backend/apps/billing/usage.py
# - backend/apps/billing/migrations/0002_add_daily_photo_limit_and_usage.py
# - backend/apps/billing/migrations/0009_remove_dailyusage_unique_user_date_and_more.py
```

---

## Troubleshooting Commands

### Check Table Existence (Failed due to auth)
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T db psql -U eatfit24 -d eatfit24 -c '\\dt billing_*'"
# Failed: role "eatfit24" does not exist (psql auth issue)
```

### List Users with Telegram IDs
```bash
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python manage.py shell -c '
from apps.users.models import User
from apps.telegram.models import TelegramUser

users = User.objects.all().order_by(\"-id\")[:3]
for u in users:
    tg = TelegramUser.objects.filter(user=u).first()
    tg_id = tg.telegram_id if tg else \"N/A\"
    print(f\"ID: {u.id}, Username: {u.username}, TG_ID: {tg_id}\")
'"
```

---

## File Operations

### Create Reports Directory
```bash
# Local command
mkdir -p reports
```

### Generate Reports
```bash
# Local Write tool commands:
# - reports/env.md
# - reports/settings-audit.md
# - reports/db-audit.md
# - reports/webhook-audit.md
# - reports/api-smoke.md
# - reports/BUG-REPORT.md
# - reports/PRODUCTION-READINESS.md
# - reports/FIX-PLAN.md
# - reports/COMMANDS-RUN.md (this file)
```

---

## Critical Finding Commands

### Confirmed P0 Bug - Table Mismatch

**Migration defines**:
```python
# backend/apps/billing/migrations/0002_add_daily_photo_limit_and_usage.py:84
'db_table': 'daily_usage',
```

**Model expects** (via Django defaults):
```python
# backend/apps/billing/usage.py:163 (Meta class has NO db_table)
# Django uses: 'billing_dailyusage'
```

**Verification commands**:
```bash
# Read migration file
cat backend/apps/billing/migrations/0002_add_daily_photo_limit_and_usage.py | grep db_table

# Read model file
cat backend/apps/billing/usage.py | grep -A 10 "class Meta"

# Attempt to query (fails)
ssh root@eatfit24.ru "cd /opt/EatFit24 && docker compose exec -T backend python manage.py shell -c 'from apps.billing.usage import DailyUsage; DailyUsage.objects.count()'"
# Result: ProgrammingError: relation "billing_dailyusage" does not exist
```

---

## Summary Statistics

**Total Commands Executed**: 40+
**SSH Sessions**: 30+
**Files Read**: 15+
**Code Files Inspected**: 10+
**Django Shell Commands**: 12+
**Critical Bug Found**: 1 (P0-001)
**Total Issues Found**: 7 (1 P0, 0 P1, 3 P2, 3 P3)

---

## Reproducibility Notes

All commands in this document can be re-run for verification:
1. Ensure SSH access to root@eatfit24.ru
2. Project must be at /opt/EatFit24
3. Docker Compose must be running
4. Some commands require .env to be configured

**Command Log End**: 2025-12-17 18:30 MSK
**Audit Duration**: ~3 hours
**Report Generation**: ~1 hour
