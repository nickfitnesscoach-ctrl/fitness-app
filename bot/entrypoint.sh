#!/bin/bash
set -e

echo "🚀 Starting bot entrypoint..."

# ============================================================
# ENVIRONMENT LOGGING (Audit Trail)
# ============================================================
echo "[BOT STARTUP] APP_ENV=${APP_ENV:-unset}"
echo "[BOT STARTUP] ENVIRONMENT=${ENVIRONMENT:-unset}"
echo "[BOT STARTUP] BACKEND_URL=${DJANGO_API_URL:-unset}"

# ============================================================
# SAFEGUARD: Prevent accidental PROD run in DEV compose
# ============================================================
if [[ "${APP_ENV}" == "prod" ]] && [[ "${DEBUG}" == "True" ]]; then
    echo "[FATAL] Safeguard triggered: APP_ENV=prod but DEBUG=True."
    echo "[FATAL] It seems you are trying to run production config in a development environment."
    exit 1
fi

if [[ "${ENVIRONMENT}" == "development" ]] && [[ "${APP_ENV}" != "dev" ]]; then
    echo "[FATAL] Safeguard triggered: ENVIRONMENT=development but APP_ENV=${APP_ENV}."
    echo "[FATAL] For local development, set APP_ENV=dev in .env.local"
    exit 1
fi


# Ждём доступности Django Backend API
echo "⏳ Waiting for Backend API to be ready..."
BACKEND_URL="${DJANGO_API_URL:-http://backend:8000/api/v1}"
HEALTH_URL="${BACKEND_URL%/api/v1}/health/"

for i in {1..30}; do
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        echo "✅ Backend API is ready!"
        break
    fi
    echo "Backend API is unavailable - attempt $i/30, sleeping..."
    sleep 2
done

if ! curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
    echo "⚠️ Backend API health check failed, but continuing to start the bot"
fi

# Запускаем бота
echo "🤖 Starting the bot..."
exec python main.py
