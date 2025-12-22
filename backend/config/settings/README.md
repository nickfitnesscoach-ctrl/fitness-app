# config/settings — документация

Эта папка содержит настройки Django, разделённые по окружениям.

## Файлы

### base.py
Общие настройки для всех окружений:
- INSTALLED_APPS, MIDDLEWARE
- DRF (REST_FRAMEWORK), throttling rates
- Celery
- общие константы
Важно: здесь НЕ задаются окружение-зависимые вещи (например Redis cache).

### local.py
Настройки для разработки на своём компьютере:
- DEBUG=True
- разрешены localhost домены
- cache = LocMem (быстро, без Redis)
- можно включить Browsable API

### production.py
Настройки для сервера (продакшен):
- DEBUG=False по умолчанию
- ALLOWED_HOSTS обязателен
- cache = Redis
- включены базовые security заголовки/флаги

### test.py
Настройки для автотестов:
- SQLite in-memory
- cache = LocMem
- быстрый хешер паролей

---

## Как выбрать окружение

Django использует переменную окружения:

DJANGO_SETTINGS_MODULE

Примеры:
- локально:
  - DJANGO_SETTINGS_MODULE=config.settings.local
- прод:
  - DJANGO_SETTINGS_MODULE=config.settings.production
- тесты:
  - DJANGO_SETTINGS_MODULE=config.settings.test

---

## Важные переменные окружения (env)

Минимально необходимые:
- SECRET_KEY (обязательно)
- ALLOWED_HOSTS (обязательно в production)

Для БД:
- POSTGRES_DB
- POSTGRES_USER
- POSTGRES_PASSWORD
- POSTGRES_HOST
- POSTGRES_PORT

Для Redis:
- REDIS_URL

Для Celery:
- CELERY_BROKER_URL
- CELERY_RESULT_BACKEND

AI:
- AI_ASYNC_ENABLED (по умолчанию True)
- AI_PROXY_URL
- AI_PROXY_SECRET

CORS:
- CORS_ALLOWED_ORIGINS (в production, список через запятую)

---

## Throttling (антиспам)

Throttling — это защита от частых запросов.
Это НЕ тарифные лимиты.

В base.py определены rates:
- ai_per_minute
- ai_per_day
- task_status (polling)
