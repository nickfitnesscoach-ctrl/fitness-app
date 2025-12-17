# Environment Inventory Report

**Date**: 2025-12-17
**Server**: eatfit24.ru
**Project Path**: /opt/EatFit24

## Docker Services Status

| Service | Image | Status | Uptime | Ports |
|---------|-------|--------|--------|-------|
| backend | eatfit24-backend | healthy | 11 minutes | 8000:8000 |
| celery-worker | eatfit24-celery-worker | healthy | 11 minutes | - |
| db | postgres:15 | healthy | 9 days | 127.0.0.1:5432 |
| redis | redis:7-alpine | healthy | 9 days | 127.0.0.1:6379 |
| frontend | eatfit24-frontend | healthy | 12 minutes | 3000:80 |
| bot | eatfit24-bot | running | 24 hours | - |

## Software Versions

- **Python**: 3.12.12
- **Django**: 6.0
- **Django REST Framework**: 3.16.1
- **YooKassa SDK**: 3.8.0
- **PostgreSQL**: 15
- **Redis**: 7-alpine

## Backend Logs Analysis

### Critical Issues Found

1. **Unapplied Model Changes**
   ```
   Your models in app(s): 'billing', 'telegram' have changes that are not yet reflected in a migration
   ```
   - Status: WARNING
   - Impact: Model changes not persisted, potential production bugs

2. **Missing Environment Variable**
   ```
   The "TELEGRAM_BOT_API_SECRET" variable is not set. Defaulting to a blank string.
   ```
   - Status: WARNING
   - Impact: Potential security issue for bot webhook validation

### Positive Findings

- All migrations applied successfully
- Gunicorn running with 5 workers
- All health checks passing
- Static files collected (166 files)

## Database Status

- PostgreSQL running stable for 9 days
- No connection errors
- Regular checkpointing active

## Redis Configuration

- maxmemory: 512mb
- maxmemory-policy: volatile-lru (CORRECT for Celery)
- Persistence: appendonly enabled

## Architecture

- **Backend**: Django 6.0 + Gunicorn (5 workers)
- **Task Queue**: Celery with Redis broker
- **Queues**: ai, billing, default
- **Celery Concurrency**: 4 workers
- **Soft Time Limit**: 120s
- **Hard Time Limit**: 150s
