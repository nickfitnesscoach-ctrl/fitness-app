#!/bin/bash
set -e

# EatFit24 Backend Entrypoint Script
# Handles: DB wait, migrations, static files, then starts gunicorn
#
# ENV VARIABLES:
# - DJANGO_SETTINGS_MODULE: Django settings module (default: config.settings.production)
# - MIGRATIONS_STRICT: If 1 (default), fail container if migrations fail. If 0, warn and continue.
# - RUN_MIGRATIONS: If 1 (default), run migrations. If 0, skip.
# - RUN_COLLECTSTATIC: If 1 (default), run collectstatic. If 0, skip.
#
# PRODUCTION SAFETY:
# - By default (MIGRATIONS_STRICT=1), container FAILS if migrations fail - prevents DB schema mismatch.
# - Set MIGRATIONS_STRICT=0 ONLY for emergency recovery scenarios.

echo "[Entrypoint] Starting EatFit24 Backend..."

# ============================================================
# Configuration
# ============================================================

export DJANGO_SETTINGS_MODULE="${DJANGO_SETTINGS_MODULE:-config.settings.production}"
MIGRATIONS_STRICT="${MIGRATIONS_STRICT:-1}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-1}"
RUN_COLLECTSTATIC="${RUN_COLLECTSTATIC:-1}"

# APP_ENV is REQUIRED - no dangerous defaults
# This prevents accidental production runs with misconfigured environment
APP_ENV="${APP_ENV:-}"
if [ -z "${APP_ENV}" ]; then
    echo "[FATAL] APP_ENV is not set. This is required."
    echo "[FATAL] Set APP_ENV=dev for development or APP_ENV=prod for production"
    echo "[FATAL] Example: Add APP_ENV=dev to your .env file"
    exit 1
fi

if [ "${APP_ENV}" != "dev" ] && [ "${APP_ENV}" != "prod" ]; then
    echo "[FATAL] APP_ENV must be 'dev' or 'prod', got: '${APP_ENV}'"
    exit 1
fi

echo "[Entrypoint] Configuration:"
echo "  - DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE"
echo "  - MIGRATIONS_STRICT=$MIGRATIONS_STRICT"
echo "  - RUN_MIGRATIONS=$RUN_MIGRATIONS"
echo "  - RUN_COLLECTSTATIC=$RUN_COLLECTSTATIC"
echo "  - APP_ENV=$APP_ENV"

# ============================================================
# ENVIRONMENT ISOLATION GUARDS (Critical P0 Security)
# ============================================================
# Log environment information for audit trail
echo "[STARTUP] APP_ENV=${APP_ENV}"
echo "[STARTUP] POSTGRES_DB=${POSTGRES_DB:-unset}"
echo "[STARTUP] YOOKASSA_MODE=${YOOKASSA_MODE:-unset}"

# Guard 1: Prevent DEV from connecting to PROD database
if [ "${APP_ENV}" = "dev" ]; then
    if [ "${POSTGRES_DB}" = "eatfit24_prod" ] || [ "${POSTGRES_DB}" = "eatfit24" ]; then
        echo "[FATAL] DEV environment cannot connect to PROD database (${POSTGRES_DB})"
        echo "[FATAL] Expected: eatfit24_dev"
        echo "[FATAL] Got: ${POSTGRES_DB}"
        exit 1
    fi
    echo "[Entrypoint] Environment isolation check passed: DEV → ${POSTGRES_DB}"
fi

# Guard 2: Prevent PROD from connecting to DEV database or using test keys
if [ "${APP_ENV}" = "prod" ]; then
    # Check database name
    if [ "${POSTGRES_DB}" = "eatfit24_dev" ] || [ "${POSTGRES_DB}" = "test" ]; then
        echo "[FATAL] PROD environment cannot connect to DEV/TEST database (${POSTGRES_DB})"
        echo "[FATAL] Expected: eatfit24_prod or eatfit24"
        echo "[FATAL] Got: ${POSTGRES_DB}"
        exit 1
    fi
    
    # Check for test payment keys (if YooKassa secret is set)
    if [ -n "${YOOKASSA_SECRET_KEY}" ]; then
        if echo "${YOOKASSA_SECRET_KEY}" | grep -q "test_"; then
            echo "[FATAL] PROD environment cannot use test YooKassa key"
            echo "[FATAL] YooKassa secret key starts with 'test_'"
            echo "[FATAL] Use live_ key for production"
            exit 1
        fi
    fi
    
    echo "[Entrypoint] Environment isolation check passed: PROD → ${POSTGRES_DB}"
fi

echo "[Entrypoint] Environment guards: PASSED ✓"


# ============================================================
# ENV/DEBUG Conflict Guard
# ============================================================
# Prevent running production with dev config or vice versa

ENV_VALUE="${ENV:-production}"
DEBUG_VALUE="${DEBUG:-false}"

# Normalize DEBUG to lowercase for comparison
DEBUG_LOWER=$(echo "$DEBUG_VALUE" | tr '[:upper:]' '[:lower:]')

if [ "$ENV_VALUE" = "local" ] && [ "$DEBUG_LOWER" = "false" ]; then
    echo "[Entrypoint] ERROR: ENV=local but DEBUG=false (conflict!)"
    echo "[Entrypoint] Local development requires DEBUG=true"
    echo "[Entrypoint] Fix: Set DEBUG=true in .env.local"
    exit 1
fi

if [ "$ENV_VALUE" = "production" ] && [ "$DEBUG_LOWER" = "true" ]; then
    echo "[Entrypoint] ERROR: ENV=production but DEBUG=true (conflict!)"
    echo "[Entrypoint] Production must have DEBUG=false for security"
    echo "[Entrypoint] Fix: Set DEBUG=false in .env"
    exit 1
fi

echo "[Entrypoint] ENV/DEBUG validation passed (ENV=$ENV_VALUE, DEBUG=$DEBUG_VALUE)"

# ============================================================
# SAFEGUARD: Prevent accidental PROD run in DEV compose
# ============================================================
if [[ "${DJANGO_SETTINGS_MODULE}" == *"local"* ]] && [ "${APP_ENV}" != "dev" ]; then
    echo "[FATAL] Safeguard triggered: Local settings detected but APP_ENV is not 'dev' (${APP_ENV})"
    echo "[FATAL] When using compose.dev.yml, ensure APP_ENV=dev in .env.local"
    exit 1
fi

# ============================================================
# Detect Service Type
# ============================================================

# If command is 'celery', skip DB-dependent initialization
# Celery workers will wait for backend service (which runs migrations)
if [ "$1" = "celery" ]; then
    echo "[Entrypoint] Celery service detected, skipping migrations/collectstatic"
    echo "[Entrypoint] Waiting briefly for backend to initialize DB..."
    sleep 5
    echo "[Entrypoint] Executing Celery command: $@"
    exec "$@"
fi

# ============================================================
# Wait for PostgreSQL (backend service only)
# ============================================================

DB_HOST="${POSTGRES_HOST:-db}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_USER="${POSTGRES_USER:-eatfit24}"
DB_NAME="${POSTGRES_DB:-eatfit24}"

echo "[Entrypoint] Waiting for PostgreSQL at $DB_HOST:$DB_PORT..."

MAX_RETRIES=30
RETRY_COUNT=0

while ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -q; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
        echo "[Entrypoint] ERROR: PostgreSQL not available after $MAX_RETRIES attempts"
        exit 1
    fi
    echo "[Entrypoint] PostgreSQL not ready, waiting... ($RETRY_COUNT/$MAX_RETRIES)"
    sleep 2
done

echo "[Entrypoint] PostgreSQL is ready!"

# ============================================================
# Run Django migrations
# ============================================================

if [ "$RUN_MIGRATIONS" = "1" ]; then
    echo "[Entrypoint] Running Django migrations..."

    if /app/.venv/bin/python manage.py migrate --settings="$DJANGO_SETTINGS_MODULE"; then
        echo "[Entrypoint] Migrations completed successfully"
    else
        if [ "$MIGRATIONS_STRICT" = "1" ]; then
            echo "[Entrypoint] ERROR: Migrations failed and MIGRATIONS_STRICT=1. Container will exit."
            echo "[Entrypoint] This prevents running with incompatible DB schema."
            echo "[Entrypoint] Set MIGRATIONS_STRICT=0 only for emergency recovery."
            exit 1
        else
            echo "[Entrypoint] WARNING: Migrations failed but MIGRATIONS_STRICT=0. Continuing anyway."
            echo "[Entrypoint] This is DANGEROUS in production - DB schema may be incompatible!"
        fi
    fi
else
    echo "[Entrypoint] Skipping migrations (RUN_MIGRATIONS=0)"
fi

# ============================================================
# Collect static files
# ============================================================

if [ "$RUN_COLLECTSTATIC" = "1" ]; then
    echo "[Entrypoint] Preparing static files directories..."

    # Ensure directories exist
    mkdir -p staticfiles media logs

    # Clean staticfiles if we can't write to it (fixes Permission denied from old root-owned files)
    if [ -d "staticfiles" ] && ! touch staticfiles/.writetest 2>/dev/null; then
        echo "[Entrypoint] WARNING: Cannot write to staticfiles/ (likely owned by root)"
        echo "[Entrypoint] Attempting to clean staticfiles/ before collection..."
        # Try to remove files we can remove
        find staticfiles -type f -writable -delete 2>/dev/null || true
        find staticfiles -type d -empty -delete 2>/dev/null || true
    else
        rm -f staticfiles/.writetest 2>/dev/null || true
    fi

    echo "[Entrypoint] Collecting static files..."

    if /app/.venv/bin/python manage.py collectstatic --noinput --settings="$DJANGO_SETTINGS_MODULE"; then
        echo "[Entrypoint] Static files collected successfully"
    else
        if [ "$MIGRATIONS_STRICT" = "1" ]; then
            echo "[Entrypoint] ERROR: collectstatic failed and MIGRATIONS_STRICT=1. Container will exit."
            echo "[Entrypoint] Static files are required for proper frontend serving."
            exit 1
        else
            echo "[Entrypoint] WARNING: collectstatic failed but MIGRATIONS_STRICT=0. Continuing anyway."
        fi
    fi
else
    echo "[Entrypoint] Skipping collectstatic (RUN_COLLECTSTATIC=0)"
fi

# ============================================================
# Start Server (backend service)
# ============================================================

# If a command was provided, execute it instead of default Gunicorn
# This allows docker-compose.dev.yml to override with runserver
if [ $# -gt 0 ]; then
    echo "[Entrypoint] Executing provided command: $@"
    exec "$@"
else
    echo "[Entrypoint] Starting Gunicorn with config gunicorn_config.py..."
    exec /app/.venv/bin/gunicorn --config gunicorn_config.py config.wsgi:application
fi
