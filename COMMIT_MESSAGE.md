# Commit Message для DEV/PROD Isolation

## Title
```
feat: implement complete DEV/PROD isolation (ТЗ v2)
```

## Body
```
BREAKING CHANGE: Physical isolation of DEV/PROD environments

This commit implements complete isolation between DEV and PROD environments
to prevent accidental data mixing and ensure safe concurrent operation.

## Critical Changes

### 1. Docker Compose Isolation (BREAKING)
- ✅ Removed all `container_name:` directives from compose.yml
- ✅ Removed `name:` from volumes and networks
- ✅ Containers now use COMPOSE_PROJECT_NAME prefixing:
  - DEV: eatfit24_dev-backend-1, eatfit24_dev-db-1, etc.
  - PROD: eatfit24-backend-1, eatfit24-db-1, etc.
- ✅ Volumes now use project prefixing:
  - DEV: eatfit24_dev_postgres_data, eatfit24_dev_redis_data
  - PROD: eatfit24_postgres_data, eatfit24_redis_data
- ✅ Networks now use project prefixing

**Migration required**: Existing deployments must migrate data from old volumes
to new prefixed volumes or set COMPOSE_PROJECT_NAME to maintain old names.

### 2. Environment Configuration
- ✅ Added APP_ENV variable (dev/prod/test) - REQUIRED
- ✅ Added COMPOSE_PROJECT_NAME - REQUIRED
- ✅ Updated .env.example with PROD defaults
- ✅ Updated .env.local with DEV defaults
- ✅ Updated .env with DEV defaults

### 3. Database Isolation
- ✅ Removed default values from compose.yml for POSTGRES_DB/USER
- ✅ All database credentials now required from .env
- ✅ DEV uses: eatfit24_dev / eatfit24_dev user
- ✅ PROD uses: eatfit24_prod / eatfit24_prod user (or custom)

### 4. Redis/Celery Isolation
- ✅ DEV: Redis DB 0 (broker), DB 1 (result_backend)
- ✅ PROD: Redis DB 1 (broker), DB 2 (result_backend)
- ✅ Removed hardcoded Celery URLs from compose.yml

### 5. PROD Guards Enhancement
- ✅ APP_ENV must be 'prod' in production.py
- ✅ YOOKASSA_MODE must be 'prod' in production.py
- ✅ DEBUG=True forbidden in production.py
- ✅ POSTGRES_DB cannot contain '_dev'/'test'/'local'
- ✅ REDIS_URL required (no defaults)
- ✅ CELERY_BROKER_URL required (no defaults)
- ✅ Test YooKassa keys (starting with 'test_') forbidden

### 6. Security Audit
- ✅ Verified WEBAPP_DEBUG_MODE_ENABLED=False in prod
- ✅ Verified no initData/headers logged
- ✅ Verified TELEGRAM_ADMINS works as list[int]

### 7. Trainer Panel API Contract
- ✅ `details` only returned with ?include_details=1
- ✅ Revenue returned as strings (not float)
- ✅ Pagination object included (total, limit, offset)

### 8. Billing Adapter
- ✅ Verified end_date=null handling (fallback to active)
- ✅ Model enforces end_date required (no null in DB)

## New Files

### Scripts
- ✅ scripts/test-isolation.sh - Test DEV/PROD physical isolation
- ✅ scripts/test-prod-guards.sh - Test PROD guards fail-fast

### Documentation
- ✅ DEV_PROD_ISOLATION_CHECKLIST.md - Complete validation checklist
- ✅ Updated CLAUDE.md - Container naming convention
- ✅ Updated .env.example - PROD environment template
- ✅ Updated .env.local - DEV environment template

## Testing

### Manual Validation
```bash
# 1. Test isolation
./scripts/test-isolation.sh

# 2. Test PROD guards
./scripts/test-prod-guards.sh

# 3. Verify volumes
docker volume ls | grep eatfit24

# 4. Verify networks
docker network ls | grep eatfit24
```

### Automated Tests
All existing tests pass:
- backend/pytest
- bot/pytest
- frontend/vitest

## Rollout Plan

### For Development
1. Update .env with APP_ENV=dev and COMPOSE_PROJECT_NAME=eatfit24_dev
2. Run: docker compose down -v (to remove old volumes)
3. Run: docker compose up -d --build
4. Verify: ./scripts/test-isolation.sh

### For Production
1. Update .env with:
   - APP_ENV=prod
   - COMPOSE_PROJECT_NAME=eatfit24  (or eatfit24_prod)
   - POSTGRES_DB=eatfit24_prod
   - YOOKASSA_MODE=prod
2. Migrate volumes (if needed):
   - Option A: Rename old volumes to match new naming
   - Option B: Backup data, recreate with new names
3. Run: docker compose up -d --build
4. Verify: ./scripts/test-isolation.sh

## Acceptance Criteria

✅ P0.1: APP_ENV in settings and guards
✅ P0.2: Env variables follow new schema
✅ P0.3: TELEGRAM_ADMINS = list[int] everywhere
✅ P0.4: COMPOSE_PROJECT_NAME physical isolation
✅ P0.5: Database isolation (names and connections)
✅ P0.6: Debug bypass disabled, no initData leaks
✅ P1.1: Celery queues use different Redis DB indexes
✅ P1.2: Trainer Panel API contract enforced
✅ P2: Billing adapter handles end_date correctly

## References

- ТЗ v2: Финальная доводка после замены файлов
- DEV_PROD_ISOLATION_CHECKLIST.md
- CLAUDE.md (updated container names)
```

## Co-authored-by
```
Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```
