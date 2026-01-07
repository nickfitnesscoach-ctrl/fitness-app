# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**EatFit24 / FoodMind** — AI-powered fitness lead generation and management platform. Monorepo with three services:
- **Backend**: Django REST API with Celery async processing
- **Bot**: Telegram bot using aiogram 3.x
- **Frontend**: React Telegram MiniApp (Vite + TypeScript)

## Quick Commands

### Backend (Django)
```bash
cd backend
python manage.py runserver              # Dev server
python manage.py test                   # Run all tests
pytest -v                               # Alternative: pytest
pytest apps/billing/tests/test_webhooks.py -v   # Single file
pytest -k "test_payment" -v                     # By pattern
python manage.py makemigrations         # Create migrations
python manage.py migrate                # Apply migrations
python manage.py migrate --plan         # Check pending migrations
ruff check .                            # Lint
black .                                 # Format
```

### Bot (Telegram)
```bash
cd bot
python main.py                          # Run bot
pytest tests/ -v                        # Run tests
alembic upgrade head                    # Apply migrations
alembic revision --autogenerate -m "description"  # Create migration
```

### Frontend (React)
```bash
cd frontend
npm run dev                             # Dev server (localhost:5173)
npm run build                           # Production build
npm run lint                            # ESLint
npm run type-check                      # TypeScript check
npm run test                            # Vitest
```

### Docker (All Services)
```bash
docker compose up -d                    # Start all services
docker compose up -d --build            # Rebuild and start
docker compose ps                       # Check status
docker compose logs -f backend          # View logs
docker compose restart backend          # Restart service
docker compose down                     # Stop all
docker compose down -v                  # Stop all and remove volumes
```

## Architecture

### Service Communication

```
Internet → Nginx → Frontend (React MiniApp)
                 → Backend API (Django + DRF)
                       ↓
              Celery Worker (async AI/billing tasks)
                       ↓
              Redis (broker) + PostgreSQL

Telegram → Bot (aiogram) → Django API
                         → PostgreSQL (direct via SQLAlchemy)
```

### Backend Structure (`backend/`)
- `apps/` — Django applications:
  - `ai/` — AI services (OpenRouter integration)
  - `ai_proxy/` — AI request proxy, rate limiting, image normalization
  - `billing/` — Subscriptions, YooKassa payments, webhooks
  - `common/` — Shared utilities and base classes
  - `core/` — Core application logic
  - `nutrition/` — Nutrition tracking
  - `telegram/` — Telegram integration endpoints
  - `users/` — User management
- `config/` — Django settings and Celery config
  - `settings/` — Split settings: `base.py`, `local.py`, `production.py`, `test.py`
  - `celery.py` — Celery configuration, task routing, beat schedule
- Celery queues: `ai`, `billing`, `default`

### Bot Structure (`bot/`)
- `app/handlers/` — Message handlers
- `app/services/` — Business logic
- `app/models/` — SQLAlchemy models
- `alembic/` — Database migrations

### Frontend Structure (`frontend/src/`)
- `pages/` — Page components
- `components/` — Reusable components
- `contexts/` — React contexts (auth, theme)
- `services/` — API integration
- `hooks/` — Custom hooks

## Critical Conventions

### Billing System
The billing module handles subscriptions, payments, and YooKassa integration. Key principles:
- **Webhook = source of truth** — Payment succeeds only after webhook confirmation
- **Price from DB** — Never trust amounts from frontend
- **YooKassaService** — Single point of integration with payment gateway
- **Atomic limits** — Race condition protection for usage limits

Detailed documentation in `backend/apps/billing/docs/`:
- `architecture.md` — Module structure
- `payment-flow.md` — Payment lifecycle
- `webhooks.md` — Webhook handling
- `security.md` — Security constraints
- `operations.md` — Operational procedures

### Time & Timezone
**"If it runs on the server — it's UTC."**
- Always use `timezone.now()` in Django, NEVER `datetime.now()`
- Database timestamps are UTC
- Celery Beat crontab uses `Europe/Moscow` (from Django TIME_ZONE)
- Frontend converts UTC to user's local timezone

### Backend Testing
```bash
cd backend
pytest -v                                        # All tests
pytest apps/billing/tests/test_webhooks.py -v   # Single file
pytest -k "test_payment" -v                     # By pattern
python manage.py test                            # Django test runner
```
Uses `config.settings.test` module. Both pytest and Django test runner are supported.

### Bot Testing
```bash
cd bot
pytest tests/ -v
pytest tests/test_critical_bugs.py::test_name -v  # Single test
```
All tests are async with mocked DB and external APIs.

### Frontend Testing
```bash
cd frontend
npm run test                    # Run once
npm run test:watch             # Watch mode
```
Uses Vitest + Testing Library.

## Environment Variables

All services read from root `.env` file. See `.env.example` for required variables.

Key variables:
- `POSTGRES_PASSWORD` — Required, shared by backend and bot
- `SECRET_KEY` — Django secret (generate with: `openssl rand -hex 32`)
- `TELEGRAM_BOT_TOKEN` — Bot token (from @BotFather)
- `TELEGRAM_BOT_API_SECRET` — Bot API secret (generate with: `openssl rand -hex 32`)
- `BOT_ADMIN_ID`, `ADMIN_IDS`, `TELEGRAM_ADMINS` — Admin Telegram IDs
- `OPENROUTER_API_KEY` — AI API key
- `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` — Payment gateway credentials
- `YOOKASSA_MODE` — `test` or `prod`
- `YOOKASSA_RETURN_URL` — Return URL after payment
- `BILLING_RECURRING_ENABLED` — `true`/`false` - enable auto-renew subscriptions
- `WEBHOOK_TRUST_XFF` — `true` in production (trust X-Forwarded-For from nginx)
- `WEBHOOK_TRUSTED_PROXIES` — Trusted proxy IPs (e.g., `127.0.0.1,172.23.0.0/16`)
- `WEB_APP_URL` — Telegram Mini App URL (e.g., `https://eatfit24.ru/app`)
- `DJANGO_API_URL` — Backend API URL for bot (e.g., `http://backend:8000/api/v1`)
- `DJANGO_SETTINGS_MODULE` — `config.settings.production` or `config.settings.local`

## Celery Tasks

Worker handles queues: `ai`, `billing`, `default`

**Worker command**: `celery -A config worker -l INFO --concurrency=2 -Q ai,billing,default`

**Task routing** (in `config/celery.py`):
- `apps.billing.webhooks.tasks.*` → `billing` queue
- `apps.billing.tasks_recurring.*` → `billing` queue
- `apps.ai.tasks.*` → `ai` queue
- Everything else → `default` queue

**Periodic tasks** (Celery Beat):
- `billing-retry-stuck-webhooks` — every 5 minutes
- `billing-alert-failed-webhooks` — every 15 minutes
- `billing-cleanup-pending-payments` — hourly
- `billing-process-due-renewals` — hourly

After modifying `config/celery.py`, reset Beat:
```bash
./scripts/reset-celery-beat.sh
```

Verify tasks are scheduled:
```bash
docker logs --tail 20 eatfit24-celery-beat-1 | grep "Sending due task"
```

## Common Development Tasks

### Database Access
```bash
# Access PostgreSQL shell
docker exec -it eatfit24-db psql -U eatfit24 -d eatfit24

# Backend: Django shell
docker exec -it eatfit24-backend-1 python manage.py shell

# Backend: Create superuser
docker exec -it eatfit24-backend-1 python manage.py createsuperuser

# Backend: Run migrations inside container
docker exec eatfit24-backend-1 python manage.py migrate

# Backend: Check pending migrations
docker exec eatfit24-backend-1 python manage.py showmigrations

# Bot: Alembic migrations
docker exec -it eatfit24-bot alembic upgrade head
```

### Logs & Debugging
```bash
# Follow logs for all services
docker compose logs -f

# Follow logs for specific service
docker compose logs -f backend
docker compose logs -f celery-worker
docker compose logs -f celery-beat

# View last N lines
docker logs --tail 50 eatfit24-backend-1

# Check Celery worker is processing tasks
docker logs --tail 100 eatfit24-celery-worker-1 | grep -E "succeeded|WEBHOOK"
```

### Health Checks
```bash
# Backend health endpoint
curl -H "Host: eatfit24.ru" http://localhost:8000/health/

# Redis
docker exec eatfit24-redis-1 redis-cli PING

# PostgreSQL
docker exec eatfit24-db-1 pg_isready -U eatfit24
```

## Container Names

Production containers (from `compose.yml`):
- `eatfit24-db` — PostgreSQL database
- `eatfit24-redis-1` — Redis (Celery broker + cache)
- `eatfit24-backend-1` — Django API (port 127.0.0.1:8000)
- `eatfit24-celery-worker-1` — Celery worker
- `eatfit24-celery-beat-1` — Celery Beat scheduler
- `eatfit24-bot` — Telegram bot
- `eatfit24-frontend` — React frontend (port 127.0.0.1:3000)

**Note:** Container names with `-1` suffix are managed by Docker Compose. Some containers use explicit `container_name` (without suffix), others get the `-1` suffix automatically.

## Utility Scripts

Located in `scripts/`:
- `pre-deploy-check.sh` — **CRITICAL**: Pre-deployment gate for backend (run before every deploy)
- `reset-celery-beat.sh` — Reset Celery Beat after schedule changes
- `check-production-health.sh` — Health check for all services
- `fix-critical-security.sh` — Security hardening script
- `fix-nginx-static.sh` — Fix nginx static file serving
- `migrate-media-to-bind-mount.sh` — Migrate media files to bind mount
- `smoke_test.sh` — End-to-end smoke tests

## Pre-Deploy Checklist (Backend)

**CRITICAL: Always run `scripts/pre-deploy-check.sh` before deploying backend changes.**

Manual verification (if script not available):

1. **Migration gate** (BLOCKER):
   ```bash
   cd backend
   python manage.py makemigrations --check --dry-run  # Must pass
   python manage.py migrate --plan                     # Check pending migrations
   python manage.py showmigrations | grep '\[ \]'     # No unapplied migrations
   ```

2. **Git status**:
   ```bash
   git status                  # Clean working tree
   git log -1                  # Verify commit to deploy
   ```

3. **Production health**:
   ```bash
   docker compose ps                                   # All services healthy
   docker exec eatfit24-backend date                   # Verify UTC
   docker exec eatfit24-redis redis-cli PING           # Redis responsive
   curl -k https://eatfit24.ru/health/ | jq .         # Health endpoint OK
   ```

## Deployment Invariants

These rules MUST be enforced to prevent production issues:

### 1. Migration Discipline

**Rule**: Production NEVER runs `makemigrations`. Migrations are generated locally and committed.

**Enforcement**:
- ✅ **CI gate**: GitHub Actions runs `makemigrations --check` on every push
- ✅ **Pre-deploy script**: `scripts/pre-deploy-check.sh` verifies no uncommitted migrations
- ✅ **Entrypoint contract**: `RUN_MIGRATIONS=1` (numeric) applies committed migrations only

**Workflow**:
```bash
# 1. Detect changes
python manage.py makemigrations --check --dry-run

# 2. Generate migration (if needed)
python manage.py makemigrations [app_name]

# 3. Review migration file
cat backend/apps/[app]/migrations/XXXX_*.py

# 4. Test locally
python manage.py migrate

# 5. Commit and deploy
git add backend/apps/*/migrations/*.py
git commit -m "feat([app]): add migration for [description]"
git push
```

**Recovery**: If uncommitted migration detected on prod:
```bash
# On local machine
python manage.py makemigrations
git add backend/apps/*/migrations/*.py
git commit -m "feat: add missing migration"
git push

# On production server
cd /opt/EatFit24
git pull
docker compose up -d backend  # Triggers migration via entrypoint.sh
```

### 2. Environment Variable Contract

**Rule**: `entrypoint.sh` expects numeric flags (1/0), not booleans (true/false).

**Required flags** (in `.env`):
```bash
RUN_MIGRATIONS=1        # NOT "true"
RUN_COLLECTSTATIC=1     # NOT "true"
MIGRATIONS_STRICT=1     # NOT "true"
```

**Why**: Shell comparison `[ "$RUN_MIGRATIONS" = "1" ]` is string-based, not truthy.

**Verification**:
```bash
# On production
docker exec eatfit24-backend env | grep "RUN_"
# Should show: RUN_MIGRATIONS=1, RUN_COLLECTSTATIC=1
```

### 3. Service Detection in Compose

**Rule**: Service commands must match entrypoint.sh detection logic.

**Example** (compose.yml):
```yaml
services:
  celery-worker:
    command: celery -A config worker ...  # ✅ Correct: starts with "celery"
    # NOT: /app/.venv/bin/celery ...      # ❌ Wrong: $1 is full path
```

**Why**: `entrypoint.sh` checks `if [ "$1" = "celery" ]` to skip migrations for Celery services.

**Verification**:
```bash
# Check actual running process
docker exec eatfit24-celery-worker ps aux | grep celery
# Should show: celery worker, NOT gunicorn
```

### 4. Memory Baseline & Alerting

**Current baseline** (as of 2026-01-07):
- `backend`: ~300MB / 1.5G (19%)
- `celery-worker`: ~270MB / 1G (27%)
- `celery-beat`: ~270MB / 512M (54%)

**Alert thresholds**:
- `backend` > 700MB → investigate memory leak
- `celery-worker` > 800MB → check AI queue backlog
- `celery-beat` > 400MB → restart service

**Monitoring** (manual for now):
```bash
docker stats --no-stream | grep eatfit24
```

### 5. Time & Timezone Invariant

**Rule**: "If it runs on the server — it's UTC."

**Configuration** (from `config/settings/base.py`):
```python
TIME_ZONE = "Europe/Moscow"  # Display timezone for Celery Beat crontab
USE_TZ = True                # Store everything in UTC internally
CELERY_TIMEZONE = TIME_ZONE  # Celery uses same display timezone
```

**Enforcement**:
- ✅ **CI guard**: GitHub Actions rejects `datetime.now()` / `datetime.utcnow()`
- ✅ **Code standard**: Always use `timezone.now()` in Django
- ✅ **Database**: All timestamps stored as UTC (PostgreSQL `timezone = 'UTC'`)
- ✅ **Celery Beat**: Crontab schedules in `Europe/Moscow`, executes in UTC
- ✅ **System clock**: Server runs in UTC (`TZ=UTC` in Docker containers)

**How it works**:
- **Storage layer** (PostgreSQL, Django ORM): Always UTC
- **Processing layer** (Python, Celery workers): Aware datetimes in UTC
- **Display layer** (Celery Beat crontab): Interprets schedules in `Europe/Moscow`
- **User layer** (Frontend): Converts UTC to user's local timezone

**Verification**:
```bash
# Server timezone (should be UTC)
docker exec eatfit24-backend date
# Expected: Wed Jan  7 12:00:00 UTC 2026

# Database timezone (should be UTC)
docker exec eatfit24-db psql -U eatfit24 -c "SHOW timezone;"
# Expected: UTC

# Django timezone config
docker exec eatfit24-backend python manage.py shell -c "from django.conf import settings; print(f'TIME_ZONE={settings.TIME_ZONE}, USE_TZ={settings.USE_TZ}')"
# Expected: TIME_ZONE=Europe/Moscow, USE_TZ=True

# Celery timezone config
docker logs eatfit24-celery-worker --tail 50 | grep -i timezone
# Expected: timezone: Europe/Moscow, enable_utc: True
```

## CI/CD Pipeline

### GitHub Actions Gates

Located in `.github/workflows/backend.yml`:

1. **Datetime guard** — blocks `datetime.now()` / `datetime.utcnow()`
2. **Migration gate** — blocks uncommitted migrations (NEW)
3. **Django checks** — validates models and settings
4. **Tests** — runs full test suite

**Status**: All gates must pass before merge to `main`.
