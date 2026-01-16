# Environment Configuration — Single Source of Truth (SSOT)

**Проект:** EatFit24
**Версия:** 3.0
**Дата:** 2026-01-12
**Статус:** ✅ Production Ready

---

## 📋 Оглавление

1. [Быстрый старт](#быстрый-старт)
2. [Философия: One ENV to Rule Them All](#философия-one-env-to-rule-them-all)
3. [Файловая структура](#файловая-структура)
4. [Окружения: DEV vs PROD](#окружения-dev-vs-prod)
5. [Environment Guards (защита от ошибок)](#environment-guards)
6. [Переменные окружения](#переменные-окружения)
7. [Docker Compose интеграция](#docker-compose-интеграция)
8. [Миграция с legacy схем](#миграция-с-legacy-схем)
9. [Troubleshooting](#troubleshooting)
10. [Best Practices](#best-practices)

---

## Быстрый старт

### 🏠 Локальная разработка

```bash
# 1. Скопируйте готовый DEV шаблон
cp .env.local .env

# 2. Запустите контейнеры
docker compose up -d

# 3. Проверьте что всё правильно
docker compose logs backend | grep "\[STARTUP\]"
# Ожидаете:
# [STARTUP] APP_ENV=dev
# [STARTUP] POSTGRES_DB=eatfit24_dev
# [STARTUP] YOOKASSA_MODE=test
# Environment guards: PASSED ✓
```

### 🚀 Production (на сервере)

```bash
# 1. Проверьте .env на production
grep -E "APP_ENV|POSTGRES_DB|YOOKASSA_MODE|DEBUG" .env

# Ожидаете:
# APP_ENV=prod
# POSTGRES_DB=eatfit24
# YOOKASSA_MODE=prod
# DEBUG=false

# 2. Запустите
docker compose up -d --build

# 3. Проверьте health
curl -H "Host: eatfit24.ru" http://localhost:8000/health/
```

---

## Философия: One ENV to Rule Them All

### Проблема (до SSOT)

**Было 3+ файла:**
- `.env` (непонятно какое окружение)
- `.env.local` (dev шаблон)
- `.env.example` (документация)

**Результат:**
- Путаница: какой файл активен?
- Дублирование: `BOT_ADMIN_ID` / `ADMIN_IDS` / `TELEGRAM_ADMINS`
- Утечки секретов: production ключи попадали в dev
- Cross-env contamination: dev использует prod базу

### Решение (SSOT v3.0)

```
┌────────────────────────────────────────────────┐
│         ОДИН АКТИВНЫЙ ФАЙЛ: .env               │
├────────────────────────────────────────────────┤
│                                                 │
│  Локально:    .env ← копия .env.local          │
│  Production:  .env ← prod переменные           │
│                                                 │
│  APP_ENV определяет окружение:                  │
│  • APP_ENV=dev  → DEV guards активны           │
│  • APP_ENV=prod → PROD guards активны          │
│                                                 │
└────────────────────────────────────────────────┘
```

**Гарантии:**
- ✅ Один источник истины (`.env`)
- ✅ Guards блокируют cross-env errors (dev → prod DB)
- ✅ Fail-fast при ошибках (контейнер не запускается)
- ✅ Нормализация переменных (одна переменная = одна цель)

---

## Файловая структура

```
eatfit24/
├── .env                # ⚡ Активный файл (НЕ в git)
│                       # Локально: копия .env.local
│                       # Production: файл с PROD переменными
│
├── .env.local          # 📝 DEV шаблон (в git)
│                       # Все DEV значения уже настроены
│                       # Секреты заменены на REPLACE_ME
│
├── .env.example        # 📖 Документация (в git)
│                       # Описание всех переменных
│                       # Плейсхолдеры для всех секретов
│
├── compose.yml         # 🐳 Базовая конфигурация
│                       # env_file: .env (читает из .env)
│
└── backend/
    └── entrypoint.sh   # 🛡️ Environment Guards
                        # Проверяет APP_ENV, POSTGRES_DB, и т.д.
```

### Правила работы с файлами

| Файл | Локально | Production | В Git | Активен? |
|------|----------|------------|-------|----------|
| `.env` | Копия .env.local | Prod значения | ❌ Нет | ✅ Да |
| `.env.local` | Используется как шаблон | Не используется | ✅ Да | ❌ Нет |
| `.env.example` | Документация | Документация | ✅ Да | ❌ Нет |

**.gitignore (обязательно):**
```gitignore
# Environment files
.env
.env.*

# Исключения (коммитятся)
!.env.local
!.env.example
```

> [!CAUTION]
> ## Production Environment (SSOT)
> 
> В production используется **ТОЛЬКО** файл `.env`:
> - Файл `.env` существует только на сервере
> - `.env` НЕ коммитится
> - Создаётся вручную из `.env.example`
> 
> ❌ **`.env.prod` НЕ используется и не должен существовать**
> ❌ **Любые `--env-file .env.prod` запрещены**
> 
> **Команда запуска production:**
> ```bash
> docker compose up -d --build
> ```
> Без `--env-file`. Docker Compose по умолчанию читает `.env` — это и есть SSOT.

---

## Окружения: DEV vs PROD

### Принцип изоляции

EatFit24 использует **двухуровневую изоляцию**:

```
┌──────────────────────────────────────────────────────────────┐
│                 ФИЗИЧЕСКАЯ ИЗОЛЯЦИЯ                          │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  DEV (Локальная машина)       PROD (Сервер eatfit24.ru)     │
│  ┌──────────────────────┐     ┌──────────────────────┐      │
│  │ Docker Desktop       │     │ Production Server    │      │
│  │                      │     │                      │      │
│  │ • PostgreSQL (dev)   │     │ • PostgreSQL (prod)  │      │
│  │ • Redis (dev)        │     │ • Redis (prod)       │      │
│  │ • Backend (dev)      │     │ • Backend (prod)     │      │
│  └──────────────────────┘     └──────────────────────┘      │
│                                                               │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                 ЛОГИЧЕСКАЯ ИЗОЛЯЦИЯ (APP_ENV)                │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  APP_ENV=dev                  APP_ENV=prod                   │
│  POSTGRES_DB=eatfit24_dev     POSTGRES_DB=eatfit24           │
│  YOOKASSA_MODE=test           YOOKASSA_MODE=prod             │
│  DEBUG=true                   DEBUG=false                    │
│                                                               │
│  🛡️ Guards проверяют соответствие переменных                 │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### Ключевые различия

| Аспект | DEV | PROD |
|--------|-----|------|
| **APP_ENV** | `dev` | `prod` |
| **DEBUG** | `true` | `false` |
| **POSTGRES_DB** | `eatfit24_dev` | `eatfit24` |
| **YOOKASSA_MODE** | `test` | `prod` |
| **YOOKASSA_SECRET_KEY** | `test_***` | `live_***` |
| **Redis DB** | 0 (broker), 1 (result) | 1 (broker), 2 (result) |
| **SECRET_KEY** | Простой (dev-secret-key) | Криптостойкий (64 hex) |
| **Сертификаты SSL** | Отключены | Обязательны |
| **SECURE_HSTS** | 0 | 31536000 (1 год) |

---

## Environment Guards

### Что это?

**Environment Guards** — это runtime проверки в `backend/entrypoint.sh`, которые **блокируют запуск** контейнера при опасной конфигурации.

**Файл:** `backend/entrypoint.sh` (строки 34-78)

### Список Guards

#### 🛡️ Guard 1: DEV → PROD Database Prevention

**Защита:** DEV не может подключиться к production базе данных

```bash
if [ "${APP_ENV}" = "dev" ]; then
    if [ "${POSTGRES_DB}" = "eatfit24_prod" ] || [ "${POSTGRES_DB}" = "eatfit24" ]; then
        echo "[FATAL] DEV environment cannot connect to PROD database"
        exit 1
    fi
fi
```

**Пример срабатывания:**
```
APP_ENV=dev
POSTGRES_DB=eatfit24  ← PROD база!

Результат:
[FATAL] DEV environment cannot connect to PROD database (eatfit24)
[FATAL] Expected: eatfit24_dev
[FATAL] Got: eatfit24
Container exits with code 1
```

#### 🛡️ Guard 2: PROD → DEV Database Prevention

**Защита:** PROD не может подключиться к dev/test базе

```bash
if [ "${APP_ENV}" = "prod" ]; then
    if [ "${POSTGRES_DB}" = "eatfit24_dev" ] || [ "${POSTGRES_DB}" = "test" ]; then
        echo "[FATAL] PROD environment cannot connect to DEV/TEST database"
        exit 1
    fi
fi
```

#### 🛡️ Guard 3: PROD Test Keys Prevention

**Защита:** PROD не может использовать тестовые ключи оплаты

```bash
if [ "${APP_ENV}" = "prod" ]; then
    if echo "${YOOKASSA_SECRET_KEY}" | grep -q "test_"; then
        echo "[FATAL] PROD cannot use test YooKassa key"
        exit 1
    fi
fi
```

#### 🛡️ Guard 4: APP_ENV Required

**Защита:** APP_ENV обязателен (нет дефолта)

```bash
APP_ENV="${APP_ENV:-}"
if [ -z "${APP_ENV}" ]; then
    echo "[FATAL] APP_ENV is not set. This is required."
    echo "[FATAL] Set APP_ENV=dev for development or APP_ENV=prod for production"
    exit 1
fi
```

### Startup Logging

При каждом запуске логируются ключевые переменные:

```bash
echo "[STARTUP] APP_ENV=${APP_ENV}"
echo "[STARTUP] POSTGRES_DB=${POSTGRES_DB:-unset}"
echo "[STARTUP] YOOKASSA_MODE=${YOOKASSA_MODE:-unset}"
echo "[STARTUP] DEBUG=${DEBUG:-unset}"
```

**Пример логов:**

DEV:
```
[STARTUP] APP_ENV=dev
[STARTUP] POSTGRES_DB=eatfit24_dev
[STARTUP] YOOKASSA_MODE=test
[STARTUP] DEBUG=true
Environment guards: PASSED ✓
```

PROD:
```
[STARTUP] APP_ENV=prod
[STARTUP] POSTGRES_DB=eatfit24
[STARTUP] YOOKASSA_MODE=prod
[STARTUP] DEBUG=false
Environment guards: PASSED ✓
```

---

## Переменные окружения

### Критические переменные (обязательны)

#### APP_ENV

**Что делает:** Определяет логическое окружение для environment guards

| Значение | Использование | Guards |
|----------|---------------|--------|
| `dev` | Локальная разработка | Блокирует `POSTGRES_DB=eatfit24` или `eatfit24_prod` |
| `prod` | Production сервер | Блокирует `POSTGRES_DB=eatfit24_dev` или `test` |

> ⚠️ **CRITICAL:** APP_ENV обязателен! Нет дефолта.
> Если не задан → контейнер падает с ошибкой.

**Где используется:**
- Environment guards в `entrypoint.sh` (строки 59-90)
- Django settings guard (`production.py:17-19`, `local.py:56-58`)
- Health check endpoint (`/health/`)

#### SECRET_KEY / DJANGO_SECRET_KEY

**Что делает:** Django secret key для криптографии

**Приоритет:**
1. `SECRET_KEY` — основной (рекомендуется)
2. `DJANGO_SECRET_KEY` — fallback для совместимости

**Требования:**
- Минимум 50 символов
- Случайная строка
- **РАЗНЫЕ** для DEV и PROD

**Генерация:**
```python
import secrets
print(secrets.token_hex(32))
```

**DEV:**
```env
SECRET_KEY=dev-secret-key-not-secure
```

**PROD:**
```env
SECRET_KEY=6d85f4831fa17f217a4a1d47b074c89de1f54ab7831efff1da5500ea224afa3b
```

#### POSTGRES_DB

**Что делает:** Имя базы данных PostgreSQL

| Окружение | Значение | Guards |
|-----------|----------|---------|
| DEV | `eatfit24_dev` | ✅ Разрешено если APP_ENV=dev |
| PROD | `eatfit24` | ✅ Разрешено если APP_ENV=prod |

**Связанные переменные:**
```env
POSTGRES_USER=eatfit24_dev      # DEV
POSTGRES_PASSWORD=***           # Разные для DEV/PROD
POSTGRES_HOST=db                # Одинаково (имя контейнера)
POSTGRES_PORT=5432              # Одинаково
```

#### YOOKASSA_MODE

**Что делает:** Режим работы платежной системы

| Значение | Использование | Guards |
|----------|---------------|---------|
| `test` | Локальная разработка, тестовые платежи | ✅ Разрешено для DEV |
| `prod` | Реальные платежи | 🛡️ PROD проверяет `test_` в YOOKASSA_SECRET_KEY |

**Связанные переменные:**
```env
YOOKASSA_SHOP_ID=***
YOOKASSA_SECRET_KEY=test_***    # DEV: начинается с test_
YOOKASSA_SECRET_KEY=live_***    # PROD: начинается с live_
```

### Полный список переменных

#### Environment & Django Core

```env
# Окружение (CRITICAL)
APP_ENV=dev|prod                              # Guards: обязателен!
ENV=local|production                          # Django settings validation
DEBUG=true|false                              # Django DEBUG mode
COMPOSE_PROJECT_NAME=eatfit24_dev|eatfit24    # Docker volumes prefix

# Django
DJANGO_SETTINGS_MODULE=config.settings.local|production  # SSOT для settings
SECRET_KEY=***                                # Django secret (CRITICAL)
ALLOWED_HOSTS=localhost,eatfit24.ru           # Разрешенные хосты
DOMAIN_NAME=localhost|eatfit24.ru             # Основной домен
```

#### Database

```env
POSTGRES_DB=eatfit24_dev|eatfit24             # Имя БД (CRITICAL)
POSTGRES_USER=eatfit24_dev|eatfit24           # Пользователь БД
POSTGRES_PASSWORD=***                         # Пароль БД (CRITICAL)
POSTGRES_HOST=db                              # Имя контейнера
POSTGRES_PORT=5432                            # Порт PostgreSQL
```

#### Redis & Celery

```env
# DEV
REDIS_URL=redis://redis:6379/0                # Broker DB
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1    # Result DB

# PROD
REDIS_URL=redis://redis:6379/1                # Broker DB
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2    # Result DB

# Common
CELERY_TIMEZONE=UTC|Europe/Moscow
```

#### Telegram

```env
TELEGRAM_BOT_TOKEN=***                        # Токен бота (CRITICAL)
TELEGRAM_BOT_API_SECRET=***                   # X-Bot-Secret auth (CRITICAL)
TELEGRAM_ADMINS=310151740                     # ID админов (через запятую)
WEB_APP_URL=https://eatfit24.ru/app           # URL WebApp
DJANGO_API_URL=http://backend:8000/api/v1     # URL Django API
```

> 💡 **Нормализация админов:**
> - ✅ Используйте: `TELEGRAM_ADMINS`
> - ❌ НЕ используйте: `BOT_ADMIN_ID`, `ADMIN_IDS` (legacy, удалены)

#### Billing (YooKassa)

```env
YOOKASSA_SHOP_ID=***                          # ID магазина
YOOKASSA_SECRET_KEY=test_***|live_***         # Ключ (CRITICAL)
YOOKASSA_MODE=test|prod                       # Режим работы (CRITICAL)
YOOKASSA_RETURN_URL=***                       # URL возврата после оплаты
YOOKASSA_WEBHOOK_URL=***                      # URL webhook
BILLING_RECURRING_ENABLED=false|true          # Автопродление
BILLING_STRICT_MODE=false|true                # Строгий режим
```

#### AI / LLM

```env
OPENROUTER_API_KEY=***                        # OpenRouter API key
AI_PROXY_URL=http://185.171.80.128:8001       # URL AI Proxy
AI_PROXY_SECRET=***                           # AI Proxy auth
AI_ASYNC_ENABLED=true                         # Async обработка
```

> 🔒 **Security:** `OPENROUTER_API_KEY` НЕ должен быть в backend!
> - Backend → AI Proxy (у AI Proxy есть ключ)
> - Bot → OpenRouter (у bot есть ключ)

#### Security (HTTPS/SSL)

```env
# DEV (relaxed)
SECURE_SSL_REDIRECT=false
SESSION_COOKIE_SECURE=false
CSRF_COOKIE_SECURE=false
SECURE_HSTS_SECONDS=0

# PROD (strict)
SECURE_SSL_REDIRECT=true
SESSION_COOKIE_SECURE=true
CSRF_COOKIE_SECURE=true
SECURE_HSTS_SECONDS=31536000              # 1 год
SECURE_HSTS_INCLUDE_SUBDOMAINS=true
SECURE_HSTS_PRELOAD=true
```

#### Entrypoint Flags

```env
RUN_MIGRATIONS=1                              # Запускать миграции (1=да, 0=нет)
RUN_COLLECTSTATIC=0|1                         # DEV=0, PROD=1
MIGRATIONS_STRICT=1                           # Падать при ошибке миграций
```

---

## Docker Compose интеграция

### Базовая схема (текущая)

```yaml
# compose.yml
services:
  backend:
    env_file: .env              # ← Читает .env
    environment:
      - APP_ENV=${APP_ENV}      # ← Из .env
      - DEBUG=${DEBUG}

  bot:
    env_file: .env              # ← Читает .env

  db:
    env_file: .env              # ← Читает .env
```

**Как запускать:**

DEV:
```bash
# .env уже содержит DEV значения (скопированные из .env.local)
docker compose up -d
```

PROD:
```bash
# .env содержит PROD значения
docker compose up -d --build
```

### Проверка переменных в контейнере

```bash
# Проверить что backend видит правильные переменные
docker exec eatfit24-backend-1 printenv | grep -E "^(APP_ENV|POSTGRES_DB|YOOKASSA_MODE|DEBUG)" | sort

# Ожидаемый результат (DEV):
# APP_ENV=dev
# DEBUG=true
# POSTGRES_DB=eatfit24_dev
# YOOKASSA_MODE=test

# Ожидаемый результат (PROD):
# APP_ENV=prod
# DEBUG=false
# POSTGRES_DB=eatfit24
# YOOKASSA_MODE=prod
```

---

## Миграция с legacy схем

### Было (legacy)

**3+ файла:**
```
.env              ← Непонятно какое окружение
.env.local        ← DEV шаблон
.env.example      ← Документация
```

**Проблемы:**
- Путаница: какой файл активен?
- Дублирование переменных
- Cross-env contamination

### Стало (SSOT v3.0)

**1 активный файл:**
```
.env              ← Активный (НЕ в git)
.env.local        ← DEV шаблон (в git)
.env.example      ← Документация (в git)
```

### Шаги миграции

#### Локально

```bash
# 1. Удалите старые файлы (если есть)
rm -f .env .env.dev .env.production

# 2. Скопируйте DEV шаблон
cp .env.local .env

# 3. Проверьте
docker compose up -d
docker compose logs backend | grep "\[STARTUP\]"
```

#### Production

```bash
# 1. Создайте резервную копию
cp .env .env.backup.$(date +%Y%m%d-%H%M%S)

# 2. Проверьте обязательные переменные
grep -E "^APP_ENV=|^POSTGRES_DB=|^YOOKASSA_MODE=|^DEBUG=" .env

# Должно быть:
# APP_ENV=prod
# POSTGRES_DB=eatfit24
# YOOKASSA_MODE=prod
# DEBUG=false

# 3. Удалите запрещённые переменные (если есть)
sed -i '/^OPENROUTER_API_KEY=/d' .env
sed -i '/^BOT_ADMIN_ID=/d' .env
sed -i '/^ADMIN_IDS=/d' .env

# 4. Добавьте недостающие (если нет)
echo "TELEGRAM_BOT_API_SECRET=<generate-new-secret>" >> .env

# 5. Перезапустите
docker compose down
docker compose up -d --build

# 6. Проверьте
curl -H "Host: eatfit24.ru" http://localhost:8000/health/
```

---

## Troubleshooting

### Контейнер не запускается

#### Проблема: "[FATAL] APP_ENV is not set"

**Симптомы:**
```
[FATAL] APP_ENV is not set. This is required.
[FATAL] Set APP_ENV=dev for development or APP_ENV=prod for production
```

**Причина:** Отсутствует `APP_ENV` в `.env`

**Решение:**
```bash
# Добавьте в .env:
APP_ENV=dev     # для локальной разработки
# или
APP_ENV=prod    # для production
```

#### Проблема: "[FATAL] DEV environment cannot connect to PROD database"

**Симптомы:**
```
[STARTUP] APP_ENV=dev
[STARTUP] POSTGRES_DB=eatfit24
[FATAL] DEV environment cannot connect to PROD database (eatfit24)
```

**Причина:** Environment guards сработали

**Решение:**
```bash
# В .env исправьте:
APP_ENV=dev
POSTGRES_DB=eatfit24_dev  # ← Должна быть DEV база

# Перезапустите
docker compose down
docker compose up -d
```

#### Проблема: "[FATAL] PROD cannot use test YooKassa key"

**Симптомы:**
```
[STARTUP] APP_ENV=prod
[FATAL] PROD cannot use test YooKassa key
```

**Причина:** Production пытается использовать тестовый ключ

**Решение:**
```bash
# В .env замените:
YOOKASSA_SECRET_KEY=live_***  # Используйте live_ ключ
YOOKASSA_MODE=prod
```

### Docker не видит изменения в .env

**Проблема:** Вы изменили `.env`, но контейнер использует старые переменные

**Причина:** Переменные окружения фиксируются при создании контейнера

**Решение:**
```bash
# Пересоздайте контейнеры (не просто restart!)
docker compose down
docker compose up -d --force-recreate

# Проверьте
docker compose logs backend | grep "\[STARTUP\]"

### Applying .env.local Changes

⚠️ Docker Compose does NOT reload `env_file` variables on `restart`.

#### ❌ This will NOT apply env changes
```bash
docker compose restart backend
```

#### ✅ Correct way
```bash
docker compose -f compose.yml -f compose.dev.yml up -d --force-recreate backend
```

#### Verification
```bash
docker compose -f compose.yml -f compose.dev.yml exec backend env | grep TELEGRAM_ADMINS
```

```

---

## Best Practices

### ✅ DO (Делайте так)

1. **Всегда проверяйте APP_ENV при старте**
   ```bash
   docker compose logs backend | grep "\[STARTUP\]"
   ```

2. **Разные пароли для DEV и PROD**
   ```env
   # DEV
   POSTGRES_PASSWORD=dev_password

   # PROD
   POSTGRES_PASSWORD=secure_random_prod_password_42chars_min
   ```

3. **Храните .env.local в Git**
   - Это шаблон для команды
   - Содержит `REPLACE_ME` плейсхолдеры
   - Помогает новым разрабам

4. **Проверяйте health check после deploy**
   ```bash
   curl https://eatfit24.ru/health/ | jq
   # Проверьте: app_env: "prod"
   ```

### ❌ DON'T (Не делайте так)

1. **НЕ коммитьте .env в Git**
   ```bash
   # ПЛОХО
   git add .env

   # ХОРОШО
   # .env уже в .gitignore
   ```

2. **НЕ используйте одинаковые БД для DEV и PROD**
   ```env
   # ОЧЕНЬ ПЛОХО
   POSTGRES_DB=eatfit24  # И для DEV и для PROD

   # ХОРОШО
   # DEV: POSTGRES_DB=eatfit24_dev
   # PROD: POSTGRES_DB=eatfit24
   ```

3. **НЕ игнорируйте environment guards**
   ```bash
   # ПЛОХО
   [FATAL] DEV environment cannot connect to PROD database
   # "Ладно, потом разберусь"

   # ХОРОШО - сразу исправляйте
   ```

4. **НЕ запускайте production без health check**
   ```bash
   # ПЛОХО
   docker compose up -d
   # И сразу ушли

   # ХОРОШО
   docker compose up -d
   sleep 5
   curl http://localhost:8000/health/
   ```

### 🔒 Security Checklist (Production)

Перед deploy проверьте:

- [ ] `APP_ENV=prod`
- [ ] `DEBUG=false`
- [ ] `POSTGRES_DB=eatfit24` (не `eatfit24_dev`)
- [ ] `SECRET_KEY` — уникальный, минимум 50 символов
- [ ] `POSTGRES_PASSWORD` — сильный, отличается от DEV
- [ ] `YOOKASSA_SECRET_KEY=live_***` (не `test_***`)
- [ ] `YOOKASSA_MODE=prod`
- [ ] `SECURE_SSL_REDIRECT=true`
- [ ] `SESSION_COOKIE_SECURE=true`
- [ ] `CSRF_COOKIE_SECURE=true`
- [ ] Health check возвращает `app_env: "prod"`

---

## Мониторинг

### Health Check Endpoint

**URL:** `https://eatfit24.ru/health/`

**Response:**
```json
{
  "status": "ok",
  "version": "1.0.0",
  "python_version": "3.12.12",
  "app_env": "prod",
  "timestamp": 1768222029,
  "checks": {
    "database": "ok",
    "redis": "ok",
    "celery": "ok"
  },
  "celery_workers": 1
}
```

**Что проверять:**

1. **`app_env`** — должно совпадать с реальным окружением
   - DEV: `"dev"`
   - PROD: `"prod"`

2. **`checks.database`** — должно быть `"ok"`
   - Если `"error"` → проблемы с PostgreSQL

3. **`checks.redis`** — должно быть `"ok"`
   - Если `"error"` → проблемы с Redis

4. **`celery_workers`** — количество активных воркеров
   - PROD: обычно ≥ 1
   - Если `0` → проверьте celery-worker контейнер

---

## FAQ

**Q: Почему нельзя использовать симлинки `.env -> .env.local`?**

A: Docker Desktop на Windows плохо работает с symlinks. Используйте копирование:
```bash
cp .env.local .env
```

---

**Q: Почему guards так строгие? Можно ли их отключить?**

A: Guards защищают от критических ошибок (DEV → PROD БД, test ключи в prod). Отключать НЕ рекомендуется. Если действительно нужно — измените `backend/entrypoint.sh`.

---

**Q: Что делать если забыл какой файл используется?**

```bash
# Проверьте логи startup
docker compose logs backend | grep "\[STARTUP\]"

# Должны увидеть реальные значения:
# [STARTUP] APP_ENV=dev
# [STARTUP] POSTGRES_DB=eatfit24_dev
```

---

**Q: Можно ли запустить production локально?**

Технически да, но не рекомендуется:
```bash
# Создайте .env с PROD переменными
# APP_ENV=prod, POSTGRES_DB=eatfit24, и т.д.

docker compose up -d

# НО это создаст путаницу и может быть опасно
```

Лучше используйте staging окружение отдельно.

---

## Статус документа

- **SSOT:** ✅ Единственный источник истины
- **Production-ready:** ✅ Проверено в production
- **Обязателен для всех окружений:** ✅ Mandatory
- **Версия:** 3.0 (2026-01-12)
- **Последнее обновление:** 2026-01-12 (объединены ENV_CONTRACT, ENV_MIGRATION_GUIDE, ENV)

---

## Связанные документы

- [API Contract: Personal Plans](api_contract_plans.md)
- [AI Proxy Documentation](AI_PROXY.md)
- [CLAUDE.md](../CLAUDE.md) — инструкции для Claude Code
