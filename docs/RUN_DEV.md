# Local Development — EatFit24

> [!IMPORTANT]
> Docker Compose **always reads `.env`** — this is the SSOT.
> The `.env.local` file is a **template only**, never used directly.

---

## Quick Start

```bash
# 1. Copy template to active file
cp .env.local .env

# 2. Edit .env — replace REPLACE_ME placeholders:
#    - TELEGRAM_BOT_TOKEN (dev bot from @BotFather)
#    - YOOKASSA_SHOP_ID / YOOKASSA_SECRET_KEY (test credentials)
#    - AI_PROXY_SECRET (if using AI features)

# 3. Start services
docker compose -f compose.yml -f compose.dev.yml up -d

# 4. Check startup
docker compose logs backend | grep "\[STARTUP\]"
# Expected: APP_ENV=dev
```

---

## Verification Checklist

```bash
# 1. All containers running
docker compose ps

# 2. Health endpoint
curl http://localhost:8000/health/
# Expected: 200 OK, {"app_env": "dev", ...}

# 3. Celery configuration
docker compose exec backend printenv | grep CELERY
# Expected:
# CELERY_BROKER_URL=redis://redis:6379/0
# CELERY_RESULT_BACKEND=redis://redis:6379/1

# 4. API accessible
curl http://localhost:8000/api/v1/billing/plans/

# 5. Frontend (if using container nginx)
curl -I http://localhost:3000/app
```

---

## Common Operations

### Apply .env changes
```bash
# IMPORTANT: `restart` does NOT reload env files!
docker compose -f compose.yml -f compose.dev.yml up -d --force-recreate backend
```

### View logs
```bash
docker compose logs -f backend
docker compose logs -f celery-worker
```

### Django management
```bash
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
docker compose exec backend python manage.py shell
docker compose exec backend python manage.py test
```

---

## Frontend Development (Vite HMR)

For hot reload, run Vite locally:

```bash
cd frontend
npm install
npm run dev
# Access at http://localhost:5173
```

Add to `.env`:
```env
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "APP_ENV is not set" | Missing in `.env` | `cp .env.local .env` |
| "Cannot connect to DB" | DB not healthy | Check `docker compose ps`, view `db` logs |
| 401 on all requests | Missing token | Add `TELEGRAM_BOT_TOKEN` to `.env` |
| Changes not applied | Used `restart` | Use `up -d --force-recreate` |

---

## Related Docs

- [ENV_SSOT.md](ENV_SSOT.md) — Environment variables reference
- [RUN_PROD.md](RUN_PROD.md) — Production deployment
