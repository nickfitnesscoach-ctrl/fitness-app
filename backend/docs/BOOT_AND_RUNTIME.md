# Backend Boot & Runtime Behavior

## Purpose

This document describes how the EatFit24 backend container starts and runs in production.

**Key principles:**
- Backend runs in Docker containers
- Designed for production deployment with fail-fast behavior
- Critical errors (migrations, collectstatic) stop container startup by default
- Logs go to stdout/stderr for container orchestration
- PostgreSQL is the only supported production database

**Audience:** DevOps engineers, system administrators, developers maintaining production deployments.

## Container Startup Sequence

The backend container follows this exact sequence during startup:

### 1. Environment Configuration
- Load `DJANGO_SETTINGS_MODULE` from environment (default: `config.settings.production`)
- Load runtime control flags: `MIGRATIONS_STRICT`, `RUN_MIGRATIONS`, `RUN_COLLECTSTATIC`
- Log configuration values to stdout

### 2. Wait for PostgreSQL
- Check PostgreSQL readiness using `pg_isready` command
- Retry up to 30 times with 2-second delays (60 seconds total timeout)
- **If PostgreSQL unavailable:** Container exits with error
- Uses connection parameters from env: `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_DB`

### 3. Run Database Migrations
**If `RUN_MIGRATIONS=1` (default):**
- Execute `python manage.py migrate --settings=$DJANGO_SETTINGS_MODULE`
- **If migrations succeed:** Continue to next step
- **If migrations fail:**
  - `MIGRATIONS_STRICT=1` (default): Container exits with error
  - `MIGRATIONS_STRICT=0`: Log WARNING and continue (emergency mode only)

**If `RUN_MIGRATIONS=0`:**
- Skip migrations entirely (log message only)

### 4. Collect Static Files
**If `RUN_COLLECTSTATIC=1` (default):**
- Execute `python manage.py collectstatic --noinput --settings=$DJANGO_SETTINGS_MODULE`
- **If collectstatic succeeds:** Continue to next step
- **If collectstatic fails:**
  - `MIGRATIONS_STRICT=1` (default): Container exits with error
  - `MIGRATIONS_STRICT=0`: Log WARNING and continue (emergency mode only)

**If `RUN_COLLECTSTATIC=0`:**
- Skip collectstatic entirely (log message only)

### 5. Start Gunicorn WSGI Server
- Execute `gunicorn --config gunicorn_config.py config.wsgi:application`
- Bind to `0.0.0.0:8000`
- Worker count: `CPU cores * 2 + 1`
- Request timeout: 140 seconds
- Logs controlled by `GUNICORN_LOG_TO_FILES` (default: stdout/stderr)

**Note:** If Gunicorn fails to start, container exits.

## Runtime Control Environment Variables

These variables control container behavior during startup and runtime:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` | Django settings module to use. Single source of truth for settings. |
| `RUN_MIGRATIONS` | `1` | Whether to run database migrations on container start. Set to `0` to skip. |
| `MIGRATIONS_STRICT` | `1` | Fail-fast mode: `1` = exit on migration/collectstatic errors, `0` = warn and continue (emergency only). |
| `RUN_COLLECTSTATIC` | `1` | Whether to run collectstatic on container start. Set to `0` to skip. |
| `GUNICORN_LOG_TO_FILES` | `0` | Gunicorn logging: `0` = stdout/stderr, `1` = write to `/app/logs/gunicorn_*.log`. |
| `DJANGO_LOG_TO_FILES` | `0` | Django logging: `0` = stdout/stderr, `1` = write to `/app/logs/django.log`. |

### Database Connection Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_HOST` | `db` | PostgreSQL hostname |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | `eatfit24` | PostgreSQL username |
| `POSTGRES_DB` | `eatfit24` | PostgreSQL database name |
| `POSTGRES_PASSWORD` | *required* | PostgreSQL password (no default in production) |

### Production Security Variables
| Variable | Default | Purpose |
|----------|---------|---------|
| `DEBUG` | `False` | Django DEBUG mode. **MUST be False in production.** |
| `SECRET_KEY` | *required* | Django secret key (no default in production) |
| `ALLOWED_HOSTS` | *required* | Comma-separated list of allowed hostnames. **Empty value causes startup failure.** |

## Logging Strategy

### Default: Container-Native Logging
- **Gunicorn:** `accesslog = "-"`, `errorlog = "-"` (stdout/stderr)
- **Django:** Console handler only, JSON format by default
- **Philosophy:** Logs are streams, not files (12-factor app)
- **Integration:** Works with `docker logs`, Kubernetes, log aggregation systems

### Optional: File-Based Logging
Set both flags to enable file-based logging:
```bash
GUNICORN_LOG_TO_FILES=1
DJANGO_LOG_TO_FILES=1
```

**Requirements:**
- Volume mount to `/app/logs/` directory
- Only use for debugging or legacy systems
- Not recommended for production deployments

### Log Directory
- `/app/logs/` directory created during Docker build
- **NOT required** for normal operation (only if file logging enabled)
- **NOT stored in git** (runtime artifact)

## Security & Stability Invariants

These rules are **NON-NEGOTIABLE** and enforced by code:

### 1. PostgreSQL Only in Production
- `config/settings/production.py` uses `django.db.backends.postgresql` exclusively
- SQLite (`django.db.backends.sqlite3`) is forbidden in production settings
- SQLite allowed only in `config/settings/local.py` (development) and `config/settings/test.py` (testing)
- `db.sqlite3` files cannot be committed to git (`.gitignore`) or included in Docker image (`.dockerignore`)

### 2. Fail-Fast on Critical Errors
- **Default behavior (`MIGRATIONS_STRICT=1`):** Container exits if migrations or collectstatic fail
- **Rationale:** Prevents running with incompatible database schema or missing static files
- **Emergency override (`MIGRATIONS_STRICT=0`):** Must be explicitly set, logs dangerous warnings

### 3. DEBUG Mode Forbidden in Production
- `DEBUG=False` enforced in `config/settings/production.py`
- `DEBUG=True` exposes sensitive information (stack traces, settings, SQL queries)
- Never set `DEBUG=1` or `DEBUG=True` in production environment

### 4. Settings Module Contract
- `DJANGO_SETTINGS_MODULE` is the single source of truth
- Container entrypoint sets this variable before any Django operations
- `manage.py` respects this variable if set, falls back to `config.settings.local` for local dev
- Never hardcode `--settings` flags in production deployment scripts

### 5. Runtime Artifacts Exclusion
- No `db.sqlite3`, `media/`, `staticfiles/`, `logs/`, `__pycache__/` in git repository
- No runtime artifacts in Docker build context (excluded by `.dockerignore`)
- Static files collected during container startup, not during build
- Media files stored in volumes, not in container image

### 6. Required Environment Variables
Production deployment **MUST** set these variables (no defaults):
- `SECRET_KEY` - random, secure value (never use default/weak values)
- `POSTGRES_PASSWORD` - strong password
- `ALLOWED_HOSTS` - explicit list of domains (empty value causes startup failure)
- `CSRF_TRUSTED_ORIGINS` - must match frontend URL
- `CORS_ALLOWED_ORIGINS` - must match frontend URL

## Failure Scenarios

### Container Exits During Startup
**Possible causes:**
1. PostgreSQL not available (timeout after 60 seconds)
2. Migrations failed and `MIGRATIONS_STRICT=1`
3. collectstatic failed and `MIGRATIONS_STRICT=1`
4. `ALLOWED_HOSTS` environment variable empty or not set
5. Required environment variables missing

**Solution:** Check container logs for specific error messages, fix environment configuration.

### Container Starts But Doesn't Respond
**Possible causes:**
1. Gunicorn bound to wrong interface (should be `0.0.0.0:8000`)
2. Network misconfiguration (port not exposed/mapped)
3. Application code errors (check Gunicorn worker logs)

**Solution:** Check `docker logs <container-id>` for Gunicorn startup messages and worker errors.

### Logs Missing
**Cause:** File-based logging enabled but no volume mount.

**Solution:** Use default stdout/stderr logging (remove `GUNICORN_LOG_TO_FILES=1` and `DJANGO_LOG_TO_FILES=1`).

## Emergency Recovery Mode

When you need to start container despite migration failures:

```bash
MIGRATIONS_STRICT=0 docker compose up backend
```

**WARNING:** This is dangerous and should only be used for:
- Emergency database recovery procedures
- Rolling back failed migrations manually
- Debugging production issues with DBA supervision

**Never use `MIGRATIONS_STRICT=0` as default configuration.**

## What This Document Is NOT

This document is:
- ❌ **NOT** a tutorial on how to develop Django applications
- ❌ **NOT** a guide for local development setup
- ❌ **NOT** a replacement for README or deployment guides
- ❌ **NOT** a proposal for architectural changes
- ❌ **NOT** documentation of "how it should be" (only "how it is")

For development setup, see project README.
For deployment procedures, see deployment documentation.
For architectural decisions, see `docs/BACKEND_PRODUCTION_FIXES_2025-12-22.md`.

## Related Documentation

- [.env.example](../.env.example) - Complete list of environment variables
- [BACKEND_PRODUCTION_FIXES_2025-12-22.md](./BACKEND_PRODUCTION_FIXES_2025-12-22.md) - Security fixes and architectural decisions
- [SQLITE_CLEANUP_2025-12-22.md](./SQLITE_CLEANUP_2025-12-22.md) - SQLite removal and runtime artifacts cleanup
- [ROOT_FILES_MAP.md](./ROOT_FILES_MAP.md) - Purpose of files in backend root directory

## Status

**Status: LOCKED**

This document reflects the current production behavior as of 2025-12-22.

**Any change to runtime logic MUST update this file.**

Changes to the following files require updating this document:
- `entrypoint.sh` - startup sequence
- `gunicorn_config.py` - Gunicorn configuration
- `config/settings/production.py` - production settings
- `Dockerfile` - container build process

Last updated: 2025-12-22
