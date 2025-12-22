# SQLite Cleanup & Runtime Artifacts - 2025-12-22

## Objective
Complete removal of SQLite from backend repository and prevention of runtime artifacts in git/Docker.

## What Was Done

### 1. SQLite Removal ✅
- ✅ Deleted `backend/db.sqlite3` from working directory
- ✅ Verified file not tracked by git (was already in .gitignore)
- ✅ Added `*.sqlite3-journal` to [.gitignore](../.gitignore)

### 2. Runtime Artifacts Protection ✅
Updated [.gitignore](../.gitignore):
- ✅ `*.sqlite3-journal` - SQLite WAL files
- ✅ `.pytest_cache/` - pytest cache directory

Updated [.dockerignore](../.dockerignore):
- ✅ `.ruff_cache/` - Ruff linter cache
- ✅ `.mypy_cache/` - MyPy type checker cache

### 3. Production Settings Verification ✅
Verified [config/settings/production.py](../config/settings/production.py):
- ✅ Only PostgreSQL database backend (line 27: `django.db.backends.postgresql`)
- ✅ No SQLite configuration present
- ✅ Database config from environment variables

Confirmed SQLite only in development:
- ✅ `config/settings/local.py` - SQLite for local dev (acceptable)
- ✅ `config/settings/test.py` - SQLite for tests (acceptable)

### 4. Bonus: Django Logging Fix ✅
Fixed Django logging in [production.py](../config/settings/production.py):
- ✅ Default: logs to stdout/stderr (Docker best practice)
- ✅ Optional: `DJANGO_LOG_TO_FILES=1` for file-based logs
- ✅ Consistent with Gunicorn logging strategy

## Protection Layers

### Layer 1: Git
`.gitignore` prevents committing:
- `db.sqlite3`
- `*.sqlite3`
- `*.sqlite3-journal`
- `.pytest_cache/`
- `.ruff_cache/`
- `.mypy_cache/`
- `logs/`
- `media/`
- `staticfiles/`

### Layer 2: Docker
`.dockerignore` prevents including in image:
- `db.sqlite3`
- `*.sqlite3`
- `media/`
- `staticfiles/`
- `logs/`
- `__pycache__/`
- `.pytest_cache/`
- `.ruff_cache/`
- `.mypy_cache/`

### Layer 3: Production Settings
`config/settings/production.py` enforces:
- PostgreSQL only (no SQLite backend)
- Database config from environment (no defaults)
- `ALLOWED_HOSTS` must be set (fails if empty)

## What This Prevents

1. ❌ SQLite files committed to git
2. ❌ SQLite files included in Docker image
3. ❌ Accidental production run on SQLite
4. ❌ Runtime artifacts (logs, media, caches) in git
5. ❌ Runtime artifacts in Docker build context
6. ❌ Disk space issues from log files in containers

## What This Enables

1. ✅ Clean separation: PostgreSQL = production, SQLite = local dev only
2. ✅ Smaller Docker images (no unnecessary files)
3. ✅ Faster Docker builds (smaller context)
4. ✅ Proper log collection from containers
5. ✅ Clean git history (no runtime artifacts)

## File Structure Summary

### ✅ Should Be in Repository
```
backend/
├── apps/                    # Application code
├── config/                  # Django settings/urls/wsgi
├── manage.py               # Django management
├── requirements.txt        # Python dependencies
├── pyproject.toml         # Tool configuration (ruff, black)
├── Dockerfile             # Container build
├── entrypoint.sh          # Container startup
├── gunicorn_config.py     # Gunicorn config
├── .gitignore             # Git ignore rules
├── .dockerignore          # Docker ignore rules
└── .env.example           # ENV template (NEW)
```

### ❌ Should NOT Be in Repository
```
backend/
├── db.sqlite3             # DELETED - local database
├── logs/                  # Runtime logs (only volume)
├── media/                 # User uploads (only volume)
├── staticfiles/           # Collected static (build artifact)
├── __pycache__/           # Python cache
├── .pytest_cache/         # Pytest cache
├── .ruff_cache/           # Ruff cache
└── .env                   # Real secrets (never commit)
```

## Verification Checklist

Run these commands to verify cleanup:

```bash
# 1. No SQLite files in working directory
cd backend
find . -name "*.sqlite3*" -type f
# Should return: empty

# 2. No SQLite files tracked by git
git ls-files | grep sqlite3
# Should return: empty

# 3. Production settings valid
python -m py_compile config/settings/production.py
# Should return: no errors

# 4. SQLite patterns in .gitignore
grep -E "sqlite3|pytest_cache" .gitignore
# Should show: db.sqlite3, *.sqlite3, *.sqlite3-journal, .pytest_cache/

# 5. Runtime artifacts in .dockerignore
grep -E "sqlite3|media|logs|cache" .dockerignore
# Should show: all runtime artifacts listed
```

## Next Deployment

Before deploying to production:

1. ✅ Verify all REQUIRED env vars in `.env.example` are set
2. ✅ Ensure PostgreSQL is configured and accessible
3. ✅ Set `MIGRATIONS_STRICT=1` (default, safe mode)
4. ✅ Set `DJANGO_LOG_TO_FILES=0` (default, stdout/stderr)
5. ✅ Set `GUNICORN_LOG_TO_FILES=0` (default, stdout/stderr)

## References

### Internal Documentation
- [BACKEND_PRODUCTION_FIXES_2025-12-22.md](./BACKEND_PRODUCTION_FIXES_2025-12-22.md) - Main production fixes documentation
- [BOOT_AND_RUNTIME.md](../BOOT_AND_RUNTIME.md) - Container startup sequence and runtime behavior (NEW)
- [ROOT_FILES_MAP.md](../ROOT_FILES_MAP.md) - Purpose of root directory files (NEW)
- [.env.example](../../.env.example) - Environment variables reference

### External Resources
- Django deployment checklist: https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/
- Twelve-Factor App: https://12factor.net/
