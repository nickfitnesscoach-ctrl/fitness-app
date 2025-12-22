# Backend Production Fixes - 2025-12-22

## Summary
Fixed critical production safety issues in backend Docker container configuration, following the same security-first approach as frontend. All changes follow "no overengineering" principle.

## Priority 0 (CRITICAL) - Fixed

### 1. Entrypoint Fail-Fast (SECURITY CRITICAL)
**Problem**: Migrations and collectstatic failures only logged WARNING and continued, allowing container to start with incompatible DB schema.

**Solution**: [entrypoint.sh](../entrypoint.sh)
- ✅ Added `MIGRATIONS_STRICT=1` (default) - container FAILS if migrations/collectstatic fail
- ✅ `MIGRATIONS_STRICT=0` - emergency mode (explicitly opt-in to dangerous behavior)
- ✅ Added `RUN_MIGRATIONS=0/1` and `RUN_COLLECTSTATIC=0/1` flags for control
- ✅ Use `DJANGO_SETTINGS_MODULE` from env instead of hardcoded `--settings=config.settings.production`

**Impact**: Prevents silent DB schema mismatches and "500 errors in production with no visible error"

### 2. Gunicorn Logs to Stdout/Stderr (Docker Best Practice)
**Problem**: Logs written to `/app/logs/*.log` files - breaks container log collection, can cause disk space issues.

**Solution**: [gunicorn_config.py](../gunicorn_config.py)
- ✅ Default: `accesslog="-"`, `errorlog="-"` (stdout/stderr)
- ✅ Optional: Set `GUNICORN_LOG_TO_FILES=1` to write to files (requires volume mount)

**Impact**: Proper log aggregation in Docker/K8s, no disk space surprises

### 3. Django Logs to Stdout (Docker Best Practice)
**Problem**: Django logging in production.py was configured to write to `/app/logs/django.log` files alongside console - same issues as Gunicorn.

**Solution**: [config/settings/production.py](../config/settings/production.py)
- ✅ Default: logs only to console (stdout/stderr)
- ✅ Optional: Set `DJANGO_LOG_TO_FILES=1` to write to files (requires volume mount)
- ✅ Dynamic handler list based on env var

**Impact**: Consistent logging strategy across all components (Django + Gunicorn), proper container log collection

## Priority 1 (HIGH) - Fixed

### 4. Settings Module Contract
**Problem**: `manage.py` defaulted to `config.settings.local`, but entrypoint used `--settings=config.settings.production` - created "dual reality".

**Solution**: [manage.py](../manage.py)
- ✅ Uses `DJANGO_SETTINGS_MODULE` env var if set (Docker always sets it)
- ✅ Falls back to `config.settings.local` for local dev
- ✅ Added documentation comments

**Impact**: Single source of truth for settings module

### 5. ENV Contract Documentation
**Problem**: No clear documentation of required/optional env variables (like frontend has).

**Solution**: [.env.example](../.env.example)
- ✅ Complete list of REQUIRED and OPTIONAL env variables
- ✅ Security checklist for production
- ✅ Clear descriptions of what each variable does
- ✅ Warnings about MIGRATIONS_STRICT and DEBUG flags

**Impact**: Clear contract, prevents misconfiguration

### 6. SQLite Cleanup (SECURITY)
**Problem**: `db.sqlite3` file existed in backend directory - risk of accidental SQLite usage in container or commits to git.

**Solution**: Complete SQLite removal
- ✅ Deleted `backend/db.sqlite3` from working directory
- ✅ Updated [.gitignore](../.gitignore) - added `*.sqlite3-journal` and `.pytest_cache/`
- ✅ Updated [.dockerignore](../.dockerignore) - added `.ruff_cache/` and `.mypy_cache/`
- ✅ Verified [production.py](../config/settings/production.py) - only PostgreSQL allowed (line 27)
- ✅ Confirmed SQLite only in `local.py` and `test.py` (dev/testing only)

**Impact**:
- ❌ Cannot accidentally run production on SQLite
- ❌ Cannot commit SQLite files to git
- ❌ Cannot include SQLite in Docker image
- ✅ Clear separation: PostgreSQL = production, SQLite = local dev/tests only

## Priority 2 (MEDIUM) - Fixed

### 7. Toolchain Cleanup
**Problem**: Both `ruff` (in pyproject.toml) AND `flake8`/`isort` (in requirements.txt) - duplicate linting tools.

**Solution**: [requirements.txt](../requirements.txt)
- ✅ Removed `flake8` and `isort`
- ✅ Added `ruff>=0.1.0` (already configured in pyproject.toml)
- ✅ Kept `black` for formatting (Ruff handles linting + imports)

**Impact**: Simpler toolchain, no conflicting lint rules

## Environment Variables Added

### Entrypoint Control
- `DJANGO_SETTINGS_MODULE` - settings module (default: `config.settings.production`)
- `MIGRATIONS_STRICT` - fail on migration errors (default: `1`)
- `RUN_MIGRATIONS` - run migrations on startup (default: `1`)
- `RUN_COLLECTSTATIC` - run collectstatic on startup (default: `1`)

### Logging Control
- `GUNICORN_LOG_TO_FILES` - write Gunicorn logs to files instead of stdout (default: `0`)
- `DJANGO_LOG_TO_FILES` - write Django logs to files instead of stdout (default: `0`)

## What This Prevents

1. ❌ Starting container with failed migrations (incompatible DB schema)
2. ❌ Silent collectstatic failures (missing static files)
3. ❌ Log files filling up disk space in containers
4. ❌ Logs not being collected by Docker/K8s
5. ❌ Confusion about which settings module is used
6. ❌ Production containers running with DEBUG=1 by accident
7. ❌ Accidental SQLite usage in production
8. ❌ SQLite files committed to git or included in Docker image

## What This Enables

1. ✅ Safe production deployments (fail-fast on errors)
2. ✅ Proper observability (stdout/stderr logs)
3. ✅ Emergency recovery mode (MIGRATIONS_STRICT=0)
4. ✅ Flexible deployment scenarios (skip migrations/collectstatic if needed)
5. ✅ Clear env variable contract (like frontend has)

## Production Deployment Checklist

Before deploying to production, ensure:

1. ✅ All REQUIRED env variables in `.env.example` are set
2. ✅ `DEBUG=0` (NEVER 1 in production)
3. ✅ `SECRET_KEY` is random and secure (not default value)
4. ✅ `MIGRATIONS_STRICT=1` (default, safe mode)
5. ✅ `GUNICORN_LOG_TO_FILES=0` (default, stdout/stderr)
6. ✅ `ALLOWED_HOSTS` contains only your domains
7. ✅ `CSRF_TRUSTED_ORIGINS` matches your frontend URL
8. ✅ `CORS_ALLOWED_ORIGINS` matches your frontend URL
9. ✅ Strong `POSTGRES_PASSWORD`
10. ✅ Production API keys (Telegram, YooKassa, OpenAI)

## Testing

Test fail-fast behavior:
```bash
# Test migration failure causes container exit
docker-compose up backend
# If migrations fail, container should exit with error

# Test emergency mode
MIGRATIONS_STRICT=0 docker-compose up backend
# If migrations fail, container continues with WARNING
```

Test log output:
```bash
# Default: logs go to docker logs
docker-compose logs -f backend

# Optional: file-based logs
GUNICORN_LOG_TO_FILES=1 docker-compose up backend
docker exec backend ls -la /app/logs/
```

## Files Changed

1. [backend/entrypoint.sh](../entrypoint.sh) - fail-fast, env-based config
2. [backend/gunicorn_config.py](../gunicorn_config.py) - stdout/stderr logs by default
3. [backend/config/settings/production.py](../config/settings/production.py) - stdout/stderr logs by default
4. [backend/manage.py](../manage.py) - settings module from env
5. [backend/requirements.txt](../requirements.txt) - removed flake8/isort, added ruff
6. [backend/.env.example](../.env.example) - NEW: env contract documentation
7. [backend/.gitignore](../.gitignore) - added `*.sqlite3-journal`, `.pytest_cache/`
8. [backend/.dockerignore](../.dockerignore) - added `.ruff_cache/`, `.mypy_cache/`
9. `backend/db.sqlite3` - DELETED (SQLite cleanup)

## Next Steps (Optional Improvements)

These are NOT urgent, but could be useful:

1. Add health check endpoint for container orchestration
2. Add structured logging (JSON format) for better log parsing
3. Add metrics export (Prometheus format)
4. Consider moving to async workers (gevent/uvicorn) if needed

## References

### Internal Documentation
- [BOOT_AND_RUNTIME.md](../BOOT_AND_RUNTIME.md) - Container startup sequence and runtime behavior (NEW)
- [ROOT_FILES_MAP.md](../ROOT_FILES_MAP.md) - Purpose of root directory files (NEW)
- [SQLITE_CLEANUP_2025-12-22.md](../SQLITE_CLEANUP_2025-12-22.md) - SQLite removal and runtime artifacts cleanup
- [.env.example](../../.env.example) - Environment variables reference
- Frontend ENV contract: [frontend/.env.example](../../../frontend/.env.example)

### External Resources
- Docker logging best practices: https://docs.docker.com/config/containers/logging/
- Twelve-Factor App methodology: https://12factor.net/
- Django deployment checklist: https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/
