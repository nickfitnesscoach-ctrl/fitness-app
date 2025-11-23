#!/bin/bash
set -e

echo "🚀 Starting bot entrypoint..."

# Ждём доступности базы данных
echo "⏳ Waiting for database to be ready..."
until pg_isready -h "${DB_HOST:-localhost}" -p "${DB_PORT:-5432}" -U "${DB_USER:-postgres}" -q; do
    echo "Database is unavailable - sleeping"
    sleep 2
done
echo "✅ Database is ready!"

# Применяем миграции с обработкой ошибок
echo "📦 Running Alembic migrations..."
if alembic upgrade head; then
    echo "✅ Migrations applied successfully"
else
    echo "⚠️ Migration failed, but continuing to start the bot"
    echo "   You may need to fix migrations manually"
fi

# Запускаем бота
echo "🤖 Starting the bot..."
exec python main.py
