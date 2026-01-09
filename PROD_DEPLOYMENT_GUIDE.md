# PROD Deployment Guide — DEV/PROD Isolation Migration

**CRITICAL**: This guide is for migrating existing PROD deployment to new isolated architecture.

⚠️ **BREAKING CHANGE**: Container names, volumes, and networks will change.

---

## Pre-Deployment Checklist

### 1️⃣ Backup Current PROD Data (MANDATORY)

**Before any changes**, backup all critical data:

```bash
# 1. List current volumes
docker volume ls | grep eatfit24
# Example output:
#   eatfit24-postgres-data
#   eatfit24-redis-data
#   eatfit24-backend-static
#   eatfit24-celerybeat-data

# 2. Backup PostgreSQL database
docker exec eatfit24-db-1 pg_dump -U eatfit24 -d eatfit24 > backup_postgres_$(date +%Y%m%d_%H%M%S).sql

# 3. Backup media files (if using volume instead of bind mount)
# Skip if using bind mount at /var/lib/eatfit24/media
docker run --rm -v eatfit24-media:/data -v $(pwd):/backup alpine tar czf /backup/backup_media_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .

# 4. Backup Redis data (optional, can be regenerated)
docker run --rm -v eatfit24-redis-data:/data -v $(pwd):/backup alpine tar czf /backup/backup_redis_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .

# 5. Backup Celery Beat schedule (optional)
docker run --rm -v eatfit24-celerybeat-data:/data -v $(pwd):/backup alpine tar czf /backup/backup_celerybeat_$(date +%Y%m%d_%H%M%S).tar.gz -C /data .

# 6. Verify backups exist
ls -lh backup_*.{sql,tar.gz}
```

**CRITICAL**: Do NOT proceed until all backups are verified!

---

### 2️⃣ Update .env on PROD Server

**Location**: `/opt/eatfit24/.env` (or your prod path)

Add/update these **REQUIRED** variables:

```bash
# ===== CRITICAL: NEW REQUIRED VARIABLES =====
APP_ENV=prod
COMPOSE_PROJECT_NAME=eatfit24

# ===== Database (must NOT contain _dev) =====
POSTGRES_DB=eatfit24_prod
POSTGRES_USER=eatfit24_prod
POSTGRES_PASSWORD=<your_secure_password>

# ===== Redis/Celery (PROD uses DB 1/2) =====
REDIS_URL=redis://:YOUR_REDIS_PASSWORD@redis:6379/1
CELERY_BROKER_URL=redis://:YOUR_REDIS_PASSWORD@redis:6379/1
CELERY_RESULT_BACKEND=redis://:YOUR_REDIS_PASSWORD@redis:6379/2

# ===== YooKassa (MUST be prod) =====
YOOKASSA_MODE=prod
YOOKASSA_SECRET_KEY=live_your_actual_key_here  # NOT test_

# ===== Django =====
DEBUG=False
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=<your_secret_key_at_least_50_chars>
ALLOWED_HOSTS=eatfit24.ru,www.eatfit24.ru

# ===== Other required vars =====
TELEGRAM_BOT_TOKEN=<your_prod_bot_token>
TELEGRAM_ADMINS=<admin_ids_comma_separated>
```

**Verify .env file**:
```bash
cat .env | grep -E "APP_ENV|COMPOSE_PROJECT_NAME|POSTGRES_DB|YOOKASSA_MODE|DEBUG"
```

Expected output:
```
APP_ENV=prod
COMPOSE_PROJECT_NAME=eatfit24
POSTGRES_DB=eatfit24_prod
YOOKASSA_MODE=prod
DEBUG=False
```

---

### 3️⃣ Stop Current PROD (DOWNTIME STARTS)

```bash
cd /opt/eatfit24  # or your prod path

# Stop all services gracefully
docker compose down

# Verify all containers stopped
docker ps -a | grep eatfit24
# Should show: Exited status
```

---

## Migration Strategy: Option A (Recommended for Minimal Downtime)

**Strategy**: Keep existing volume names using `COMPOSE_PROJECT_NAME=eatfit24` (without `_prod` suffix).

This avoids data migration and matches old container names closely.

### Steps:

1. **Update compose.yml** (already done in this commit)
   - Removed all `container_name:` directives
   - Removed `name:` from volumes/networks

2. **Set COMPOSE_PROJECT_NAME=eatfit24** (in .env)
   ```bash
   # This will create containers like:
   # eatfit24-backend-1  (close to old eatfit24-backend)
   # eatfit24-db-1       (close to old eatfit24-db)
   ```

3. **Rename database to avoid _dev guard**
   ```bash
   # Connect to PostgreSQL
   docker compose up -d db
   docker exec -it eatfit24-db-1 psql -U eatfit24 -d postgres

   # Inside psql:
   ALTER DATABASE eatfit24 RENAME TO eatfit24_prod;
   \q

   # Stop DB
   docker compose down
   ```

4. **Pull latest code and rebuild**
   ```bash
   git pull
   docker compose build --no-cache
   ```

5. **Start with new isolation**
   ```bash
   docker compose up -d --build
   ```

6. **Verify startup**
   ```bash
   # Check containers
   docker compose ps
   # All should be "Up" or "healthy"

   # Check logs for guards
   docker compose logs backend | head -n 50
   # Should NOT see RuntimeError about guards

   # Verify database
   docker compose exec backend python -c "from django.conf import settings; print(f'APP_ENV={settings.APP_ENV}, DB={settings.DATABASES[\"default\"][\"NAME\"]}')"
   # Expected: APP_ENV=prod, DB=eatfit24_prod

   # Verify no debug bypass
   docker compose exec backend python -c "from django.conf import settings; assert not getattr(settings, 'WEBAPP_DEBUG_MODE_ENABLED', False); print('✓ Debug bypass disabled')"
   # Expected: ✓ Debug bypass disabled
   ```

---

## Migration Strategy: Option B (Full Isolation, Requires Data Migration)

**Strategy**: Use `COMPOSE_PROJECT_NAME=eatfit24_prod` for complete separation.

Requires migrating data from old volumes to new ones.

### Steps:

1. **Set COMPOSE_PROJECT_NAME=eatfit24_prod** (in .env)

2. **Create new volumes and restore data**
   ```bash
   # Start only database to create new volumes
   docker compose up -d db

   # Restore PostgreSQL backup
   cat backup_postgres_YYYYMMDD_HHMMSS.sql | docker exec -i eatfit24_prod-db-1 psql -U eatfit24_prod -d eatfit24_prod

   # Restore Redis (optional)
   docker run --rm -v eatfit24_prod_redis_data:/data -v $(pwd):/backup alpine tar xzf /backup/backup_redis_YYYYMMDD_HHMMSS.tar.gz -C /data

   # Restore Celery Beat (optional)
   docker run --rm -v eatfit24_prod_celerybeat_data:/data -v $(pwd):/backup alpine tar xzf /backup/backup_celerybeat_YYYYMMDD_HHMMSS.tar.gz -C /data
   ```

3. **Start all services**
   ```bash
   docker compose up -d --build
   ```

4. **Verify as in Option A**

---

## 4️⃣ Post-Deployment Sanity Checks

### Critical Checks (MUST PASS before considering deployment successful)

```bash
# 1. Health endpoint
curl -k https://eatfit24.ru/health/ | jq .
# Expected: {"status": "healthy", ...}

# 2. Plans API
curl -k https://eatfit24.ru/api/billing/plans/ | jq .
# Expected: list of plans

# 3. Verify PROD mode in logs
docker compose logs backend | grep -i "APP_ENV\|YOOKASSA_MODE"
# Should show: prod, NOT dev/test

# 4. Verify no test payment UI
# Open frontend and check that test payment card is NOT visible

# 5. Celery worker is alive
docker compose logs celery-worker | tail -n 20
# Should show: "Connected to redis://redis:6379/1"
# Should NOT show errors

# 6. Celery Beat is scheduling
docker compose logs celery-beat | grep "Sending due task"
# Should show scheduled tasks

# 7. Database isolation check
docker compose exec backend python -c "
from django.conf import settings
db_name = settings.DATABASES['default']['NAME']
assert '_dev' not in db_name, f'ERROR: DB name contains _dev: {db_name}'
assert settings.APP_ENV == 'prod', f'ERROR: APP_ENV is not prod: {settings.APP_ENV}'
print(f'✓ Isolation verified: DB={db_name}, APP_ENV={settings.APP_ENV}')
"
# Expected: ✓ Isolation verified: DB=eatfit24_prod, APP_ENV=prod

# 8. PROD guards are active
docker compose exec backend python -c "
from django.conf import settings
assert not settings.DEBUG, 'ERROR: DEBUG=True in production'
assert not getattr(settings, 'WEBAPP_DEBUG_MODE_ENABLED', False), 'ERROR: Debug bypass enabled'
assert settings.YOOKASSA_MODE == 'prod', 'ERROR: YooKassa not in prod mode'
print('✓ All PROD guards active')
"
# Expected: ✓ All PROD guards active
```

### Functional Checks (Business Logic)

```bash
# 1. Test payment creation (with real user)
# Use Telegram bot to create payment
# Verify payment appears in database

# 2. Test webhook (if you have test webhook URL)
# Send test webhook to https://eatfit24.ru/api/billing/webhook/yookassa/
# Verify it's processed correctly

# 3. Test panel access
# Login to trainer panel via Telegram
# Verify applications/clients/subscribers load

# 4. Test AI requests
# Send photo to bot
# Verify AI analysis works
```

---

## 5️⃣ Rollback Plan (If Something Goes Wrong)

If deployment fails and you need to rollback:

```bash
# 1. Stop new deployment
docker compose down

# 2. Restore old .env (if you backed it up)
mv .env.backup.old .env

# 3. Checkout previous commit
git checkout <previous_commit_hash>

# 4. Restore database from backup
cat backup_postgres_YYYYMMDD_HHMMSS.sql | docker exec -i eatfit24-db-1 psql -U eatfit24 -d eatfit24

# 5. Start old deployment
docker compose up -d --build

# 6. Verify old deployment works
curl -k https://eatfit24.ru/health/
```

---

## 6️⃣ Cleanup Old Volumes (AFTER Successful Migration)

**WAIT AT LEAST 7 DAYS** after successful migration before deleting old volumes.

```bash
# List old volumes
docker volume ls | grep eatfit24 | grep -v "eatfit24_prod\|eatfit24-"

# Delete old volumes (ONLY after confirming new deployment is stable)
# docker volume rm eatfit24-old-volume-name
```

---

## 7️⃣ Update Monitoring/Alerts

If you have monitoring configured:

- Update container names in monitoring queries
- Update volume names in disk usage alerts
- Update service names in uptime checks

Old names:
- `eatfit24-backend` → `eatfit24-backend-1` (Option A) or `eatfit24_prod-backend-1` (Option B)
- `eatfit24-db` → `eatfit24-db-1` (Option A) or `eatfit24_prod-db-1` (Option B)

---

## Troubleshooting

### Problem: Backend fails to start with "APP_ENV must be 'prod'"

**Solution**: Check `.env` file:
```bash
grep APP_ENV .env
# Must show: APP_ENV=prod
```

### Problem: Backend fails with "Forbidden DB name"

**Solution**: Database name contains `_dev`. Rename it:
```bash
docker compose exec db psql -U postgres -c "ALTER DATABASE eatfit24_dev RENAME TO eatfit24_prod;"
```

Update `.env`:
```bash
POSTGRES_DB=eatfit24_prod
```

### Problem: "REDIS_URL must be set"

**Solution**: Add to `.env`:
```bash
REDIS_URL=redis://:YOUR_PASSWORD@redis:6379/1
CELERY_BROKER_URL=redis://:YOUR_PASSWORD@redis:6379/1
CELERY_RESULT_BACKEND=redis://:YOUR_PASSWORD@redis:6379/2
```

### Problem: Containers have wrong names

**Solution**: Check `COMPOSE_PROJECT_NAME` in `.env`:
```bash
grep COMPOSE_PROJECT_NAME .env
# Should show: COMPOSE_PROJECT_NAME=eatfit24  (or eatfit24_prod)
```

Recreate containers:
```bash
docker compose down -v
docker compose up -d --build
```

---

## Summary

✅ **Before deployment**:
- Backup database (mandatory)
- Backup volumes (recommended)
- Update .env with required variables
- Choose migration strategy (Option A or B)

✅ **During deployment**:
- Stop current PROD
- Apply migrations (if using Option B)
- Start new deployment
- Run sanity checks

✅ **After deployment**:
- Monitor for 24-48 hours
- Keep backups for at least 7 days
- Update monitoring/alerts
- Clean up old volumes (after 7+ days)

---

## Need Help?

1. Check logs: `docker compose logs -f backend`
2. Run isolation test: `./scripts/test-isolation.sh`
3. Run guards test: `./scripts/test-prod-guards.sh`
4. Review: [DEV_PROD_ISOLATION_CHECKLIST.md](DEV_PROD_ISOLATION_CHECKLIST.md)
