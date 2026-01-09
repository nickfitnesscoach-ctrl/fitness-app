# Deployment Runbook

This runbook provides step-by-step procedures for deploying EatFit24 services to production.

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Backend Deployment](#backend-deployment)
3. [Bot Deployment](#bot-deployment)
4. [Frontend Deployment](#frontend-deployment)
5. [Full Stack Deployment](#full-stack-deployment)
6. [Rollback Procedures](#rollback-procedures)
7. [Post-Deployment Verification](#post-deployment-verification)

---

## Pre-Deployment Checklist

**CRITICAL**: Always run these checks before deploying:

```bash
# 1. Run pre-deploy script (LOCAL)
cd /path/to/eatfit24
./scripts/pre-deploy-check.sh

# 2. Ensure you're on the correct branch
git branch
# Expected: main (or feature branch if deploying to staging)

# 3. Ensure all changes are committed
git status
# Expected: "working tree clean"

# 4. Ensure local is synced with remote
git pull
git push

# 5. Verify CI pipeline passed
# Check GitHub Actions: https://github.com/your-org/eatfit24/actions
```

### Environment Contracts (Deterministic Deployment)

**Rule**: Always pin compose file + env file explicitly to eliminate directory-dependent behavior.

```bash
# ✅ DETERMINISTIC (works from any directory)
docker compose -f /opt/eatfit24/compose.yml --env-file /opt/eatfit24/.env up -d

# ✅ Also acceptable (if you cd first)
cd /opt/eatfit24
docker compose up -d
```

**Why**: Eliminates "wrong directory / wrong .env / wrong project" issues.

**Verify effective config before deploy**:
```bash
# Check that environment is loaded correctly
docker compose -f /opt/eatfit24/compose.yml --env-file /opt/eatfit24/.env config \
  | grep -E "(APP_ENV|DJANGO_SETTINGS_MODULE|SECRET_KEY|ALLOWED_HOSTS|POSTGRES_DB|REDIS_URL)" -n

# If you see expected values → safe to proceed
```

---

## Backend Deployment

### Standard Backend Deployment

```bash
# 1. SSH to production server
ssh eatfit24  # or: ssh deploy@eatfit24.ru

# 2. Navigate to project directory
cd /opt/eatfit24

# 3. Pull latest code
git pull

# 4. Check for pending migrations
docker compose exec -T backend python manage.py showmigrations --plan | tail -50

# 5. Rebuild and restart backend
docker compose up -d backend --build

# 6. Verify deployment
docker compose ps
docker logs eatfit24-backend-1 --tail 50

# 7. Test health endpoint
curl https://eatfit24.ru/health/
# Expected: {"status":"ok",...}

# 8. Verify migrations applied
docker logs eatfit24-backend-1 2>&1 | grep -A 5 "Running migrations"
# Expected: "No migrations to apply" or list of applied migrations
```

### Emergency Backend Restart (No Code Changes)

```bash
cd /opt/eatfit24
docker compose restart backend

# Or with health check wait:
docker compose restart backend && sleep 5 && curl https://eatfit24.ru/health/
```

### Backend with Celery Restart

```bash
cd /opt/eatfit24

# Restart all backend services
docker compose restart backend celery-worker celery-beat

# Verify
docker compose ps
docker logs eatfit24-celery-worker-1 --tail 20
docker logs eatfit24-celery-beat-1 --tail 20
```

---

## Bot Deployment

### Standard Bot Deployment

```bash
# 1. SSH to production
ssh eatfit24

# 2. Navigate to project
cd /opt/eatfit24

# 3. Pull latest code
git pull

# 4. Check for pending Alembic migrations
docker compose exec bot alembic current
docker compose exec bot alembic history | head -10

# 5. Rebuild and restart bot
docker compose up -d bot --build

# 6. Verify deployment
docker compose ps
docker logs eatfit24-bot-1 --tail 50

# 7. Test bot is responsive
# Send /start to bot in Telegram
```

### Bot Database Migrations

```bash
cd /opt/eatfit24

# Apply migrations
docker compose exec bot alembic upgrade head

# Verify current version
docker compose exec bot alembic current

# Restart bot
docker compose restart bot
```

---

## Frontend Deployment

### Standard Frontend Deployment

```bash
# 1. SSH to production
ssh eatfit24

# 2. Navigate to project
cd /opt/eatfit24

# 3. Pull latest code
git pull

# 4. Rebuild and restart frontend
docker compose up -d frontend --build

# 5. Verify deployment
docker compose ps
docker logs eatfit24-frontend-1 --tail 20

# 6. Test frontend
curl -I https://eatfit24.ru/app/
# Expected: HTTP/2 200
```

---

## Full Stack Deployment

Use this when deploying changes across multiple services:

```bash
# 1. SSH to production
ssh eatfit24

# 2. Navigate to project
cd /opt/eatfit24

# 3. Pull latest code
git pull

# 4. Verify effective config before deploy
docker compose config | grep -E "(SECRET_KEY|POSTGRES_DB|DJANGO_SETTINGS_MODULE)" | head -10
# Expected: See correct values loaded

# 5. Check environment variables for duplicates
grep -E "^(SECRET_KEY|POSTGRES_PASSWORD|TELEGRAM_BOT_TOKEN)=" .env | wc -l
# Expected: 3 (each variable present once)

# 6. Rebuild all services
docker compose build

# 7. Restart all services
docker compose up -d

# 8. Verify all services healthy
docker compose ps

# 9. Check logs for errors
docker compose logs --tail 50

# 10. Run health checks
curl https://eatfit24.ru/health/
curl -I https://eatfit24.ru/app/
# Test bot: Send /start in Telegram

# 11. Verify Celery workers
docker logs eatfit24-celery-worker-1 --tail 20 | grep "ready"
docker logs eatfit24-celery-beat-1 --tail 20 | grep "beat"
```

---

## Rollback Procedures

### Backend Rollback

```bash
cd /opt/eatfit24

# 1. Identify last working commit
git log --oneline -10

# 2. Checkout previous commit
git checkout <commit-hash>

# 3. Check if migrations need rollback
docker compose exec backend python manage.py showmigrations

# 4. If needed, rollback migrations
docker compose exec backend python manage.py migrate <app_name> <previous_migration_number>

# 5. Rebuild and restart
docker compose up -d backend --build

# 6. Verify
curl https://eatfit24.ru/health/
```

### Full Stack Rollback

```bash
cd /opt/eatfit24

# 1. Checkout previous commit
git checkout <commit-hash>

# 2. Rebuild and restart all
docker compose down
docker compose up -d --build

# 3. Verify
docker compose ps
curl https://eatfit24.ru/health/
```

### Database Rollback (DANGEROUS)

**WARNING**: Only use in emergency. Always backup first.

```bash
# 1. Backup database
docker exec eatfit24-db-1 pg_dump -U eatfit24 eatfit24 > backup_$(date +%Y%m%d_%H%M%S).sql

# 2. Rollback migrations
docker compose exec backend python manage.py migrate <app> <migration_name>

# 3. Restart backend
docker compose restart backend
```

---

## Post-Deployment Verification

Run these checks after every deployment:

### Quick Health Check

```bash
# 1. All containers running
docker compose ps
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -i restart || echo "✅ No restarts detected"
# Expected: All containers healthy, no unexpected restarts

# 2. Backend health
curl https://eatfit24.ru/health/
# Expected: {"status":"ok",...}

# 3. Frontend accessible
curl -I https://eatfit24.ru/app/
# Expected: HTTP/2 200

# 4. Bot responsive
# Send /start to @eatfit24_bot
# Expected: Bot responds
```

### Detailed Verification

```bash
# 1. Check for errors in logs (last 5 minutes)
docker compose logs --since 5m | grep -i error

# 2. Check backend startup
docker logs eatfit24-backend-1 --tail 50 | grep -E "Starting|Booting|Migrations"

# 3. Check Celery workers
docker logs eatfit24-celery-worker-1 --tail 20 | grep "ready"
docker logs eatfit24-celery-beat-1 --tail 20 | grep "Scheduler"

# 4. Check database connectivity
docker compose exec backend python manage.py dbshell -c "SELECT 1;"

# 5. Check Redis connectivity
docker compose exec redis redis-cli PING
# Expected: PONG

# 6. Test API endpoint (with auth)
curl -H "Authorization: Bearer <token>" https://eatfit24.ru/api/v1/users/me/
# Expected: User data or 401 if not authenticated
```

### Monitoring & Alerting

```bash
# Check memory usage
docker stats --no-stream | grep eatfit24

# Check disk space
df -h | grep -E "Filesystem|/opt"

# Check recent restarts (should be none)
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -i "restart"
```

---

## Common Issues & Solutions

### Issue: Backend fails to start with "SECRET_KEY not configured"

**Cause**: Settings file has early imports that access Django settings before `django.setup()`

**Solution**:
```bash
# 1. Check for forbidden imports in settings
grep -r "from apps\." backend/config/settings/

# 2. Run smoke test locally
cd backend
python -c "import django; django.setup(); print('OK')"

# 3. See backend/docs/ENV_CONTRACT.md for rules
```

### Issue: Migrations fail with "relation already exists"

**Cause**: Migration already applied but Django thinks it's not

**Solution**:
```bash
# Fake the migration
docker compose exec backend python manage.py migrate --fake <app> <migration>
```

### Issue: Container keeps restarting

**Cause**: Usually entrypoint script failing

**Solution**:
```bash
# Check logs
docker logs eatfit24-<service>-1 --tail 100

# Common fixes:
# 1. Check environment variables
docker compose exec <service> env | grep -E "SECRET_KEY|POSTGRES"

# 2. Check database connectivity
docker compose exec <service> nc -zv db 5432

# 3. Check permissions
docker compose exec <service> ls -la /app
```

### Issue: Wrong .env file loaded

**Cause**: Ran `docker compose` from wrong directory

**Solution**:
```bash
# Always CD to project root first
cd /opt/eatfit24
docker compose up -d

# Verify .env location
docker compose exec backend env | head -20
```

---

## Incident Response Contacts

**Primary**: Telegram @admin_username
**Secondary**: Email admin@eatfit24.ru

**Escalation Matrix**:
1. Backend issues → Backend team lead
2. Database issues → DevOps + Backend lead
3. Payment issues → Billing lead + DevOps
4. Security incidents → All hands + immediate lockdown

---

## Related Documentation

- [CLAUDE.md](CLAUDE.md) - Development commands & architecture
- [backend/docs/ENV_CONTRACT.md](backend/docs/ENV_CONTRACT.md) - Settings rules & contracts
- [backend/apps/billing/docs/operations.md](backend/apps/billing/docs/operations.md) - Billing operations
- [scripts/pre-deploy-check.sh](scripts/pre-deploy-check.sh) - Pre-deployment validation

---

**Last updated**: 2026-01-09
**Maintained by**: DevOps Team
