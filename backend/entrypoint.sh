#!/bin/bash
set -e

# EatFit24 Backend Entrypoint Script
# Handles: DB wait, migrations, static files, then starts gunicorn
#
# NOTE:
# - This script is used inside the backend Docker container for EatFit24.
# - It waits for PostgreSQL, runs migrations + collectstatic, then starts Gunicorn.
# - Migration / static failures DO NOT stop the container (they log WARNING and continue).

echo "[Entrypoint] Starting EatFit24 Backend..."

# ============================================================
# Wait for PostgreSQL
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

echo "[Entrypoint] Running Django migrations (production settings)..."

if python manage.py migrate --settings=config.settings.production; then
    echo "[Entrypoint] Migrations completed successfully"
else
    echo "[Entrypoint] WARNING: Migrations failed, backend will still start. CHECK LOGS!"
    # Don't exit - let the app try to start
fi

# ============================================================
# Collect static files
# ============================================================

echo "[Entrypoint] Collecting static files..."

if python manage.py collectstatic --noinput --settings=config.settings.production; then
    echo "[Entrypoint] Static files collected successfully"
else
    echo "[Entrypoint] WARNING: collectstatic failed, continuing without updated static files"
fi

# ============================================================
# Start Gunicorn
# ============================================================

echo "[Entrypoint] Starting Gunicorn with config gunicorn_config.py..."
exec gunicorn --config gunicorn_config.py config.wsgi:application
