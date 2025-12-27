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
  - `ai_proxy/` — AI request proxy and rate limiting
  - `billing/` — Subscriptions, YooKassa payments, webhooks
  - `common/` — Shared utilities and base classes
  - `core/` — Core application logic
  - `nutrition/` — Nutrition tracking
  - `telegram/` — Telegram integration endpoints
  - `users/` — User management
- `config/` — Django settings and Celery config
  - `settings/` — Split settings: `base.py`, `local.py`, `production.py`, `test.py`
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
- `OPENROUTER_API_KEY` — AI API key
- `YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY` — Payment gateway credentials
- `YOOKASSA_MODE` — `test` or `prod`
- `BILLING_RECURRING_ENABLED` — `true`/`false` - enable auto-renew subscriptions
- `WEBHOOK_TRUST_XFF` — `true` in production (trust X-Forwarded-For from nginx)
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
- `eatfit24-redis` — Redis (Celery broker + cache)
- `eatfit24-backend` — Django API (port 127.0.0.1:8000)
- `eatfit24-celery-worker` — Celery worker
- `eatfit24-celery-beat` — Celery Beat scheduler
- `eatfit24-bot` — Telegram bot
- `eatfit24-frontend` — React frontend (port 127.0.0.1:3000)

## Utility Scripts

Located in `scripts/`:
- `reset-celery-beat.sh` — Reset Celery Beat after schedule changes
- `check-production-health.sh` — Health check for all services
- `fix-critical-security.sh` — Security hardening script
- `smoke_test.sh` — End-to-end smoke tests

## Pre-Deploy Checklist (Backend)

1. `git status` — clean working tree
2. `docker compose ps` — all services healthy
3. `docker exec eatfit24-backend-1 date` — verify UTC
4. `python manage.py migrate --plan` — check pending migrations
5. `docker exec eatfit24-redis-1 redis-cli PING` — Redis responsive
