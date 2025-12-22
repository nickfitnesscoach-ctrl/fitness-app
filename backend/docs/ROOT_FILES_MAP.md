# Backend Root Files Map

## Purpose

Quick reference for files in `backend/` root directory - what they do and whether they can be modified.

## Files Overview

| File | Purpose | Can Modify? | Notes |
|------|---------|-------------|-------|
| `Dockerfile` | Builds backend Docker image | ⚠️ Carefully | Multi-stage build. Changes affect image size and startup. |
| `entrypoint.sh` | Container startup script | ⚠️ Carefully | Controls migrations, collectstatic, Gunicorn start. Critical for production. |
| `gunicorn_config.py` | WSGI server configuration | ⚠️ Carefully | Worker count, timeouts, logging. Affects performance and observability. |
| `manage.py` | Django CLI entry point | ✅ Rarely | Standard Django file. Uses `DJANGO_SETTINGS_MODULE` from env. |
| `requirements.txt` | Python dependencies | ✅ Yes | Add/update packages here. Run `pip install -r requirements.txt` after changes. |
| `pyproject.toml` | Tool configuration | ✅ Yes | Ruff, Black settings. Safe to modify linting rules. |
| `.gitignore` | Git exclusion rules | ✅ Yes | Protects against committing runtime artifacts (db.sqlite3, logs, media). |
| `.dockerignore` | Docker build context exclusion | ✅ Yes | Keeps Docker build context small. Excludes docs, tests, caches. |
| `.env.example` | Environment variables template | ✅ Yes | Document new required/optional env vars here. Never contains real secrets. |
| `nginx-host.conf` | Nginx configuration example | ✅ Yes | Example only, not used by backend container. For reference/deployment. |
| `db.sqlite3` | ❌ **NOT USED** | ❌ **FORBIDDEN** | SQLite database. Production uses PostgreSQL only. Must not exist. |

## Directories Overview

| Directory | Purpose | Can Modify? | Notes |
|-----------|---------|-------------|-------|
| `apps/` | Django applications code | ✅ Yes | Domain logic (billing, nutrition, telegram, ai, etc.) |
| `config/` | Django project settings | ⚠️ Carefully | `settings/`, `urls.py`, `wsgi.py`. Changes affect all environments. |
| `docs/` | Documentation | ✅ Yes | Excluded from Docker build (`.dockerignore`). Safe to add/modify. |
| `logs/` | Runtime log files | ❌ Created at runtime | Not in git. Created by Docker if file logging enabled. Use stdout/stderr instead. |
| `media/` | User-uploaded files | ❌ Volume mount | Not in git. Managed by Django. Must be volume in production. |
| `staticfiles/` | Collected static files | ❌ Build artifact | Not in git. Created by `collectstatic` during container startup. |

## Critical Files (Production Impact)

These files directly affect production behavior. Changes require thorough testing:

### `entrypoint.sh`
**What it does:**
- Waits for PostgreSQL
- Runs migrations (controlled by `RUN_MIGRATIONS` and `MIGRATIONS_STRICT`)
- Runs collectstatic (controlled by `RUN_COLLECTSTATIC`)
- Starts Gunicorn

**Change impact:** Can break container startup, cause data loss, or create deployment issues.

**Testing required:** Full deployment test with real database.

### `gunicorn_config.py`
**What it does:**
- Configures worker count (affects concurrency and resource usage)
- Sets request timeout (affects long-running operations)
- Controls logging destination (stdout/stderr vs files)

**Change impact:** Can cause performance degradation, request timeouts, or missing logs.

**Testing required:** Load testing, log collection verification.

### `Dockerfile`
**What it does:**
- Multi-stage build (builder + runtime)
- Installs system dependencies (PostgreSQL client, libpq5)
- Copies application code
- Creates necessary directories (`logs/`, `staticfiles/`, `media/`)

**Change impact:** Can increase image size, break dependencies, or cause missing files.

**Testing required:** Full image build, container startup, functionality verification.

### `config/settings/production.py`
**What it does:**
- Database configuration (PostgreSQL only)
- Security settings (ALLOWED_HOSTS, CSRF, CORS, HSTS)
- Logging configuration (stdout/stderr by default)
- Cache configuration (Redis)

**Change impact:** Security vulnerabilities, database connection failures, authentication issues.

**Testing required:** Security audit, integration testing, deployment verification.

## Files That Should NOT Exist

These files/directories must not be present in the repository:

| File/Directory | Why Forbidden | Protected By |
|----------------|---------------|--------------|
| `db.sqlite3` | Production uses PostgreSQL only | `.gitignore`, `.dockerignore` |
| `*.sqlite3-journal` | SQLite temporary files | `.gitignore` |
| `.env` | Contains real secrets | `.gitignore` |
| `logs/*.log` | Runtime artifacts | `.gitignore`, `.dockerignore` |
| `media/*` | User uploads (except .gitkeep) | `.gitignore`, `.dockerignore` |
| `staticfiles/*` | Build artifacts | `.gitignore`, `.dockerignore` |
| `__pycache__/` | Python bytecode cache | `.gitignore`, `.dockerignore` |
| `.pytest_cache/` | Pytest cache | `.gitignore`, `.dockerignore` |
| `.ruff_cache/` | Ruff linter cache | `.gitignore`, `.dockerignore` |
| `.mypy_cache/` | MyPy type checker cache | `.gitignore`, `.dockerignore` |

## Modification Safety Guide

### ✅ Safe to Modify Without Risk
- `docs/` - Documentation files
- `pyproject.toml` - Linter/formatter settings
- `.env.example` - Environment variable template (no secrets)
- `README.md` - Project documentation

### ⚠️ Modify With Caution (Test Required)
- `requirements.txt` - Adding packages can introduce vulnerabilities or conflicts
- `manage.py` - Rarely needed, but changes affect Django CLI
- `.gitignore` / `.dockerignore` - Removing entries can leak sensitive data
- `config/urls.py` - URL routing changes affect API endpoints
- `apps/` code - Business logic changes, require thorough testing

### 🚨 Critical Files (Production Testing Required)
- `Dockerfile` - Affects all deployments
- `entrypoint.sh` - Controls container startup
- `gunicorn_config.py` - Affects performance and stability
- `config/settings/production.py` - Security and database configuration
- `config/wsgi.py` - WSGI application entry point

## Quick Reference

**Want to add a Python package?**
→ Edit `requirements.txt`, rebuild Docker image.

**Want to change linting rules?**
→ Edit `pyproject.toml`, run `ruff check`.

**Want to add environment variable?**
→ Update `.env.example` with description, document in `BOOT_AND_RUNTIME.md`.

**Want to change startup behavior?**
→ Edit `entrypoint.sh`, test full deployment cycle, update `BOOT_AND_RUNTIME.md`.

**Want to change worker count or timeout?**
→ Edit `gunicorn_config.py`, load test thoroughly.

**Want to change logging?**
→ Edit `gunicorn_config.py` and/or `config/settings/production.py`, verify log collection works.

## Related Documentation

- [BOOT_AND_RUNTIME.md](./BOOT_AND_RUNTIME.md) - Container startup sequence and runtime behavior
- [BACKEND_PRODUCTION_FIXES_2025-12-22.md](./BACKEND_PRODUCTION_FIXES_2025-12-22.md) - Recent production fixes
- [.env.example](../.env.example) - Complete environment variables reference

## Status

**Status: LOCKED**

This document reflects the current file structure as of 2025-12-22.

**Any addition/removal of root files MUST update this document.**

Last updated: 2025-12-22
