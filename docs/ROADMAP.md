# Infrastructure SSOT Refactoring — Roadmap

> **Date:** 2026-01-16  
> **Status:** ✅ Complete

---

## Summary

| Priority | Task | Status | Risk |
|----------|------|--------|------|
| **P0** | SSOT Production Compose | ✅ Done | - |
| **P0** | Gunicorn OOM Safety | ✅ Done | Low |
| **P0** | Security Rotation Runbook | ✅ Done | - |
| **P1** | Celery Cleanup | ✅ Done | Low |
| **P1** | Documentation SSOT | ✅ Done | - |
| **P2** | deploy.resources docs | Backlog | Very Low |

---

## Completed Changes

### P0-1: SSOT Production Compose

✅ **Decision:** Variant A
- `compose.yml` = Production SSOT
- `compose.dev.yml` = Dev overrides only
- `compose.prod.yml` → Archived to `docs/archive/compose.prod.yml.deprecated`

**Conflicts resolved:**

| Conflict | Resolution |
|----------|------------|
| container_name hardcoding | Removed (use COMPOSE_PROJECT_NAME) |
| volume name hardcoding | Removed (use COMPOSE_PROJECT_NAME) |
| Redis DB `/0` vs `/1`,`/2` | Use `.env` values |
| env_file `.env.prod` | **Forbidden** — use `.env` |

---

### P0-2: Gunicorn OOM Safety

✅ **Fixed:** `backend/gunicorn_config.py`

**Before:**
```python
workers = multiprocessing.cpu_count() * 2 + 1
```

**After:**
```python
# Reads WEB_CONCURRENCY or GUNICORN_WORKERS from env
# Default: 2 workers
# Hard cap: 4 workers
workers = _get_workers()
```

---

### P0-3: Security Rotation Runbook

✅ **Created:** `docs/SECURITY_ROTATE_SECRETS.md`

Covers:
- SECRET_KEY / DJANGO_SECRET_KEY
- POSTGRES_PASSWORD
- TELEGRAM_BOT_TOKEN
- TELEGRAM_BOT_API_SECRET
- YOOKASSA_SECRET_KEY
- AI_PROXY_SECRET
- OPENROUTER_API_KEY

---

### P1-1: Celery Cleanup

✅ **Fixed:** `backend/config/celery.py`

Changes:
- `Celery("foodmind")` → `Celery("eatfit24")`
- Removed `os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")`
- Added fail-fast check: raises RuntimeError if DJANGO_SETTINGS_MODULE not set
- Updated docstring and comments

---

### P1-2: Documentation SSOT

✅ **Created:**
- `docs/RUN_PROD.md` — Production deployment SSOT
- `docs/RUN_DEV.md` — Local development SSOT
- `docs/SECURITY_ROTATE_SECRETS.md` — Secret rotation procedures
- `docs/archive/README.md` — Deprecation notes

---

## Smoke Test Checklist

### Production (on server)

```bash
# 1. Containers healthy
docker compose ps

# 2. Health endpoint
curl -H "Host: eatfit24.ru" -H "X-Forwarded-Proto: https" http://localhost:8000/health/
# Expected: 200 OK

# 3. Frontend
curl -I http://localhost:3000/app

# 4. API proxy
curl -H "Host: eatfit24.ru" http://localhost:3000/api/v1/health/

# 5. Celery queues (in logs)
docker compose logs celery-worker | grep -E "queue|ai,billing,default"

# 6. Redis DB indices
docker compose exec backend printenv | grep CELERY
# CELERY_BROKER_URL=redis://redis:6379/1
# CELERY_RESULT_BACKEND=redis://redis:6379/2
```

### Development (local)

```bash
# 1. Start
cp .env.local .env\r\ndocker compose -f compose.yml -f compose.dev.yml up -d

# 2. Health
curl http://localhost:8000/health/

# 3. Redis DB indices
docker compose exec backend printenv | grep CELERY
# CELERY_BROKER_URL=redis://redis:6379/0
# CELERY_RESULT_BACKEND=redis://redis:6379/1
```

---

## P2 (Backlog)

- [ ] Document `deploy.resources.limits` behavior (doesn't work in non-swarm mode)
- [ ] Consolidate nginx timeouts between host and container
