# LEGACY MIGRATIONS

⚠️ **These migrations are no longer used.**

The bot now uses Django backend API instead of direct database access.

## Архитектурное изменение

С версии рефакторинга (26 ноября 2025) бот **не работает с БД напрямую**:

- ❌ Старая архитектура: Bot → SQLAlchemy → PostgreSQL
- ✅ Новая архитектура: Bot → HTTP API → Django → PostgreSQL

## Данные

Все таблицы бота (users, survey_answers, plans) теперь управляются Django:

- `users` → `telegram_telegramuser` + `auth_user`
- `survey_answers` → `telegram_personalplansurvey`
- `plans` → `telegram_personalplan`

## Для справки

Эти миграции сохранены только для исторической справки.

Если нужно мигрировать старые данные, используйте:
```bash
cd backend
python manage.py migrate_bot_data --bot-db-url="postgresql+asyncpg://user:pass@host:port/dbname"
```

---

**Дата архивирования**: 26 ноября 2025
