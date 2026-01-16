# Production Deployment — EatFit24

## SSOT Command (One-liner)

```bash
docker compose up -d --build
```

> **Prerequisite:** `.env` file configured with `APP_ENV=prod` (see [ENV_SSOT.md](ENV_SSOT.md))

---

## Before Deployment Checklist

```bash
# 1. Verify production env values
grep -E "^(APP_ENV|POSTGRES_DB|YOOKASSA_MODE|DEBUG)=" .env
# Expected:
# APP_ENV=prod
# POSTGRES_DB=eatfit24
# YOOKASSA_MODE=prod
# DEBUG=false

# 2. Verify no test keys
grep -E "^YOOKASSA_SECRET_KEY=" .env | grep -v "live_" && echo "WARNING: Not a live key!"
```

---

## Deployment

```bash
# Pull latest code
git pull origin main

# Rebuild and restart (one command)
docker compose up -d --build

# Check status
docker compose ps
```

---

## Post-Deployment Verification

```bash
# 1. All containers healthy
docker compose ps
# Expected: All services UP, healthy

# 2. Health endpoint
curl -H "Host: eatfit24.ru" -H "X-Forwarded-Proto: https" http://localhost:8000/health/
# Expected: 200 OK, {"app_env": "prod", ...}

# 3. Frontend serves app
curl -I http://localhost:3000/app
# Expected: 200 OK

# 4. API proxy works
curl -H "Host: eatfit24.ru" http://localhost:3000/api/v1/billing/plans/
# Expected: 200 OK

# 5. Celery worker queues
docker compose logs celery-worker --tail 50 | grep -E "queue|ready"
# Expected: "ai,billing,default" in logs

# 6. Redis uses correct DB indices
docker compose exec backend printenv | grep CELERY
# Expected:
# CELERY_BROKER_URL=redis://redis:6379/1
# CELERY_RESULT_BACKEND=redis://redis:6379/2

# 7. Check startup guards passed
docker compose logs backend | grep "\[STARTUP\]"
# Expected: APP_ENV=prod, Environment guards: PASSED ✓
```

---

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|--------------|-----|
| Container won't start | Missing `.env` or `APP_ENV` | Check `.env` exists and has `APP_ENV=prod` |
| Guard error: "DEV database" | `POSTGRES_DB=eatfit24_dev` | Set `POSTGRES_DB=eatfit24` |
| Guard error: "test YooKassa key" | `YOOKASSA_SECRET_KEY=test_*` | Use `live_*` key |
| 502 from nginx | Backend not healthy | `docker compose logs backend` |

---

## Related Docs

- [ENV_SSOT.md](ENV_SSOT.md) — Environment variables reference
- [OPS_RUNBOOK.md](OPS_RUNBOOK.md) — Operations procedures
- [SECURITY_ROTATE_SECRETS.md](SECURITY_ROTATE_SECRETS.md) — Secret rotation
