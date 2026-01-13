# Backend — Environment Variables Contract

**Последнее обновление**: 2026-01-11
**Статус**: ✅ SSOT (Single Source of Truth)

---

## Цель документа

Этот документ определяет:
- **Обязательные** переменные окружения для backend
- **Опциональные** переменные с дефолтами
- **Запрещённые** переменные (security / architecture separation)
- Правила валидации и fail-fast в production

---

## Обязательные переменные

### APP_ENV (обязательно)

```bash
APP_ENV=prod          # Safety check в production.py
```

**Валидация**:
- `production.py` требует `APP_ENV=prod` (fail-fast если != prod)
- Без этой переменной backend не запустится

**Где используется**:
- [config/settings/production.py:17-19](../config/settings/production.py) — fail-fast проверка
- [config/settings/local.py:56-58](../config/settings/local.py) — защита от prod в dev
- [apps/telegram/auth/authentication.py:58,247](../apps/telegram/auth/authentication.py) — WebApp debug mode bypass

---

### SECRET_KEY

```bash
SECRET_KEY=<64-символа-hex>
```

**Генерация**: `openssl rand -hex 32`

**Валидация**:
- Не может быть пустым в production
- Должен быть уникальным и случайным (≥32 символа)

**Где используется**: [config/settings/base.py:35](../config/settings/base.py)

---

### ALLOWED_HOSTS

```bash
ALLOWED_HOSTS=eatfit24.ru,www.eatfit24.ru
```

**Важно**:
- Только реальные домены сайта (минимум для безопасности)
- `backend` и `localhost` НЕ нужны (healthcheck использует `Host: eatfit24.ru` header)
- В production обязательно указать реальные домены

**Валидация**: `production.py` требует непустой список

**Где используется**: [config/settings/production.py:31-34](../config/settings/production.py)

---

### POSTGRES_DB / POSTGRES_USER / POSTGRES_PASSWORD

```bash
POSTGRES_DB=eatfit24
POSTGRES_USER=eatfit24
POSTGRES_PASSWORD=<secure-password>
POSTGRES_HOST=db
POSTGRES_PORT=5432
```

**Валидация** (production.py):
- Все три обязательны и непусты
- `POSTGRES_DB` не должно содержать: `_dev`, `test`, `local`

**Где используется**: [config/settings/production.py:40-62](../config/settings/production.py)

---

### REDIS_URL

```bash
REDIS_URL=redis://redis:6379/1
```

**Формат**: `redis://[password@]host:port/db`

**Валидация**: Обязателен и непуст в production

**Где используется**:
- Cache: [config/settings/production.py:68-79](../config/settings/production.py)
- Celery broker/backend через `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND`

---

### TELEGRAM_BOT_TOKEN

```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

**Получение**: @BotFather в Telegram

**Валидация**: Обязателен в production, используется для HMAC WebApp auth

**Где используется**: [config/settings/production.py:115-119](../config/settings/production.py)

---

### TELEGRAM_ADMINS

```bash
TELEGRAM_ADMINS=310151740,987654321
```

**Формат**: Telegram user IDs через запятую (int)

**Browser Debug Mode (DEV only)**: Для работы панели тренера в браузере без Telegram добавьте `999999999` в список:
```bash
TELEGRAM_ADMINS=310151740,999999999  # DEV only
```

**Важно**: Это единственная переменная для admin IDs. Не используйте:
- ❌ `BOT_ADMIN_ID` (deprecated)
- ❌ `ADMIN_IDS` (deprecated)

**Где используется**: [config/settings/base.py:307](../config/settings/base.py)

---

### YooKassa (YOOKASSA_*)

```bash
YOOKASSA_SHOP_ID=1195531
YOOKASSA_SECRET_KEY=live_4L-wGK3jmv1tiT-_OQXw4M06W49gdtVZ1dOaZ4SZsaI
YOOKASSA_MODE=prod
YOOKASSA_RETURN_URL=https://eatfit24.ru/payment-success
YOOKASSA_WEBHOOK_URL=https://eatfit24.ru/api/billing/webhook/yookassa/
```

**Валидация** (production.py):
- `YOOKASSA_MODE` должен быть `prod` (не `test`)
- `YOOKASSA_SECRET_KEY` не может начинаться с `test_`
- Все credentials обязательны и непусты

**Где используется**: [config/settings/production.py:125-143](../config/settings/production.py)

---

### AI_PROXY_URL / AI_PROXY_SECRET

```bash
AI_PROXY_URL=http://185.171.80.128:8001
AI_PROXY_SECRET=c6b837b17429b1e7b488cc6333759dce6a326b9f6cee73a1c228670867a44a5c
```

**Важно**:
- `AI_PROXY_URL` — внешний сервер, НЕ docker internal DNS
- `AI_PROXY_SECRET` должен совпадать с `API_PROXY_SECRET` на ai-proxy сервере

**Где используется**: [config/settings/base.py:279-281](../config/settings/base.py)

---

## Опциональные переменные (с дефолтами)

### Celery

```bash
CELERY_BROKER_URL=redis://redis:6379/1       # default from REDIS_URL
CELERY_RESULT_BACKEND=redis://redis:6379/2   # default from REDIS_URL
CELERY_TIMEZONE=Europe/Moscow                # default: UTC
```

**Где используется**: [config/settings/base.py:314-322](../config/settings/base.py)

---

### Security (CSRF / CORS)

```bash
CSRF_TRUSTED_ORIGINS=https://eatfit24.ru,https://www.eatfit24.ru
CORS_ALLOWED_ORIGINS=https://eatfit24.ru,https://www.eatfit24.ru
```

**Дефолты**:
- `CSRF_TRUSTED_ORIGINS`: auto-генерируется из `ALLOWED_HOSTS` (https://)
- `CORS_ALLOWED_ORIGINS`: пустой список (требует явного указания)

**Где используется**:
- CSRF: [config/settings/production.py:98-105](../config/settings/production.py)
- CORS: [config/settings/base.py:236-240](../config/settings/base.py)

---

### Billing Flags

```bash
BILLING_RECURRING_ENABLED=true
BILLING_STRICT_MODE=true
BILLING_LOG_EVENTS=true
```

**Дефолты**: все `false`

**Где используется**: [config/settings/production.py:145](../config/settings/production.py), [config/settings/base.py:329](../config/settings/base.py)

---

### ENV (опционально)

```bash
ENV=prod  # Для validation в entrypoint.sh (не используется в Python коде)
```

**Дефолт**: не используется (опциональная переменная)

**Назначение**: Используется в `backend/entrypoint.sh` для валидации окружения (проверка консистентности `ENV` + `DEBUG`).

**Важно**: В Python коде используется `DJANGO_SETTINGS_MODULE` (SSOT для выбора settings) и `APP_ENV` (safety check).

**Где используется**: [entrypoint.sh:46-59](../entrypoint.sh)

---

### Service Flags

```bash
RUN_MIGRATIONS=1
RUN_COLLECTSTATIC=1
MIGRATIONS_STRICT=1
```

**Тип**: Numeric (1/0), НЕ boolean (true/false)

**Где используется**: `backend/entrypoint.sh`

---

### Trusted Proxies

```bash
TRUSTED_PROXIES_ENABLED=true
TRUSTED_PROXIES=172.0.0.0/8
```

**Дефолт**: `false` и пустой список

**Где используется**: [config/settings/base.py:271-272](../config/settings/base.py)

---

### Static / Media

```bash
STATIC_URL=/static/
STATIC_ROOT=/app/staticfiles
MEDIA_URL=/media/
MEDIA_ROOT=/app/media
STATICFILES_STORAGE=whitenoise.storage.CompressedManifestStaticFilesStorage
```

**Дефолты**: указаны выше

**Где используется**: [config/settings/base.py:153-166](../config/settings/base.py)

---

## Запрещённые переменные для Backend

Backend **НЕ ДОЛЖЕН** содержать:

### ❌ OPENROUTER_API_KEY
**Причина**: Backend не вызывает OpenRouter напрямую
- Фото-анализ: backend -> ai-proxy (у ai-proxy есть ключ)
- План питания: генерируется в bot (у bot есть ключ)

### ❌ OPENAI_API_KEY
**Причина**: Используется только в ai-proxy

### ❌ BOT_ADMIN_ID / ADMIN_IDS
**Причина**: Дублируют `TELEGRAM_ADMINS`
- Используйте **только** `TELEGRAM_ADMINS`
- `BOT_ADMIN_ID` / `ADMIN_IDS` deprecated

### ❌ DATABASE_URL
**Причина**: Backend использует `POSTGRES_*` напрямую
- `DATABASE_URL` не используется в коде
- Упрощает конфигурацию (один SSOT)

### ❌ DJANGO_CACHE_BACKEND
**Причина**: Backend использует `REDIS_URL` для кеша
- Дублирование с `REDIS_URL`
- Используйте только `REDIS_URL`

---

## Правила валидации (production.py)

### Fail-Fast при старте

Backend **не запустится**, если:
1. `APP_ENV != "prod"`
2. `SECRET_KEY` пустой или отсутствует
3. `ALLOWED_HOSTS` пустой
4. `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` пусты
5. `POSTGRES_DB` содержит `_dev`, `test`, `local`
6. `REDIS_URL` пустой
7. `TELEGRAM_BOT_TOKEN` пустой
8. `YOOKASSA_MODE != "prod"`
9. `YOOKASSA_SECRET_KEY` начинается с `test_`
10. `YOOKASSA_SHOP_ID` / `YOOKASSA_SECRET_KEY` пусты
11. `DEBUG=True` в production

**Где**: [config/settings/production.py](../config/settings/production.py)

---

## Примеры конфигурации

### Production (.env на сервере)

```bash
# Environment
ENV=prod
APP_ENV=prod
DEBUG=false
DJANGO_SETTINGS_MODULE=config.settings.production

# Django Core
SECRET_KEY=<generated-with-openssl-rand-hex-32>
ALLOWED_HOSTS=eatfit24.ru,www.eatfit24.ru

# Database
POSTGRES_DB=eatfit24
POSTGRES_USER=eatfit24
POSTGRES_PASSWORD=<secure-password>
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Redis / Celery
REDIS_URL=redis://redis:6379/1
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# Telegram
TELEGRAM_BOT_TOKEN=<from-botfather>
TELEGRAM_ADMINS=310151740

# YooKassa
YOOKASSA_SHOP_ID=1195531
YOOKASSA_SECRET_KEY=live_...
YOOKASSA_MODE=prod
YOOKASSA_RETURN_URL=https://eatfit24.ru/payment-success
YOOKASSA_WEBHOOK_URL=https://eatfit24.ru/api/billing/webhook/yookassa/

# AI Proxy
AI_PROXY_URL=http://185.171.80.128:8001
AI_PROXY_SECRET=<shared-with-ai-proxy>
```

---

## См. также

- [backend/.env.example](../.env.example) — шаблон переменных окружения
- [config/settings/production.py](../config/settings/production.py) — валидация
- [config/settings/base.py](../config/settings/base.py) — общие настройки
- [../../docs/ENV.md](../../docs/ENV.md) — общая документация по окружению
