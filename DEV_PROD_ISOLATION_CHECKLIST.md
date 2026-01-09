# DEV/PROD Isolation Checklist — Final Report

**Date**: 2026-01-09
**Status**: ✅ **COMPLETED**

Этот документ содержит результаты финальной доводки изоляции DEV/PROD окружений согласно ТЗ v2.

---

## ✅ P0: Критические исправления (COMPLETED)

### P0.1: APP_ENV в settings ✅

**Требование**: `APP_ENV` должен быть доступен как `settings.APP_ENV` и использоваться в guards.

**Выполнено**:
- ✅ `.env.example`: добавлен `APP_ENV=prod`
- ✅ `.env.local`: добавлен `APP_ENV=dev` (пользователем)
- ✅ `.env`: добавлен `APP_ENV=dev`
- ✅ `config/settings/base.py`: APP_ENV определён через `os.getenv("APP_ENV")`
- ✅ `config/settings/local.py`: APP_ENV явно установлен с проверкой
- ✅ `config/settings/production.py`: APP_ENV проверяется guard'ом (строка 17-19)

**Проверка**:
```bash
# DEV
docker compose exec backend python -c "from django.conf import settings; print(settings.APP_ENV)"
# Expected: dev

# PROD
docker compose exec backend python -c "from django.conf import settings; print(settings.APP_ENV)"
# Expected: prod
```

---

### P0.2: Env переменные приведены к новой схеме ✅

**Требование**:
- `CELERY_BROKER_URL` и `CELERY_RESULT_BACKEND` без дефолтов (обязательны)
- `YOOKASSA_MODE` в prod должен быть `prod`
- `REDIS_URL` обязателен в prod

**Выполнено**:
- ✅ `.env.example` обновлён:
  - `REDIS_URL=redis://:PASSWORD@redis:6379/1` (PROD)
  - `CELERY_BROKER_URL=redis://:PASSWORD@redis:6379/1` (PROD)
  - `CELERY_RESULT_BACKEND=redis://:PASSWORD@redis:6379/2` (PROD)
  - `YOOKASSA_MODE=prod`
- ✅ `.env.local` уже содержит:
  - `REDIS_URL=redis://redis:6379/0` (DEV)
  - `CELERY_BROKER_URL=redis://redis:6379/0` (DEV)
  - `CELERY_RESULT_BACKEND=redis://redis:6379/1` (DEV)
  - `YOOKASSA_MODE=test`
- ✅ `production.py` guards проверяют эти переменные (строки 67-69, 130-132)

**Проверка**:
```bash
# PROD должен падать без этих переменных
docker compose up backend
# Если REDIS_URL/CELERY_BROKER_URL отсутствует → RuntimeError
```

---

### P0.3: TELEGRAM_ADMINS = list[int] ✅

**Требование**: Убедиться, что нигде не используется `.split()` на `TELEGRAM_ADMINS`.

**Выполнено**:
- ✅ `config/settings/base.py:298`: `TELEGRAM_ADMINS: list[int] = _env_int_list("TELEGRAM_ADMINS")`
- ✅ Все места использования проверены:
  - `apps/telegram/auth/views.py:57`: функция `_parse_admin_ids()` корректно обрабатывает list/set/str
  - `apps/telegram/telegram_auth.py:52`: функция `_parse_telegram_admins()` корректно обрабатывает list/set
  - `apps/billing/notifications.py:172`: функция `_parse_admin_ids()` корректно обрабатывает list/set/str
  - `apps/billing/webhooks/tasks.py:184`: проверка `isinstance(admin_ids, str)` перед `.split()`
  - `apps/billing/views.py:730-731`: использует `in` для проверки (работает с list/set)

**Проверка**:
```bash
docker compose exec backend python -c "from django.conf import settings; print(type(settings.TELEGRAM_ADMINS), settings.TELEGRAM_ADMINS)"
# Expected: <class 'list'> [310151740]
```

---

### P0.4: COMPOSE_PROJECT_NAME для DEV/PROD изоляции ✅

**Требование**: Физическая изоляция volumes/networks/containers через `COMPOSE_PROJECT_NAME`.

**Выполнено**:
- ✅ `.env.example`: `COMPOSE_PROJECT_NAME=eatfit24_prod`
- ✅ `.env.local`: `COMPOSE_PROJECT_NAME=eatfit24_dev`
- ✅ `.env`: `COMPOSE_PROJECT_NAME=eatfit24_dev`
- ✅ **CRITICAL FIX**: Убраны все `container_name:`, `name:` параметры из `compose.yml`
  - Volumes теперь автоматически получают префикс проекта
  - Networks теперь автоматически получают префикс проекта
  - Containers теперь автоматически получают префикс проекта

**Проверка**:
```bash
# 1. Если оба окружения подняты
docker compose ls
# Expected: два разных проекта (eatfit24_dev и eatfit24_prod)

# 2. Volumes должны иметь префикс проекта
docker volume ls | grep eatfit24
# Expected DEV: eatfit24_dev_postgres_data, eatfit24_dev_redis_data, etc.
# Expected PROD: eatfit24_postgres_data, eatfit24_redis_data, etc.

# 3. Networks должны иметь префикс проекта
docker network ls | grep eatfit24
# Expected DEV: eatfit24_dev_eatfit24-network
# Expected PROD: eatfit24_eatfit24-network

# 4. Containers должны иметь префикс проекта
docker ps -a | grep eatfit24
# Expected DEV: eatfit24_dev-backend-1, eatfit24_dev-db-1, etc.
# Expected PROD: eatfit24-backend-1, eatfit24-db-1, etc.

# 5. Automated test script
./scripts/test-isolation.sh
```

---

### P0.5: Изоляция баз данных ✅

**Требование**: Базы реально разные (имена и подключения).

**Выполнено**:
- ✅ `compose.yml` исправлен:
  - Убраны дефолты `eatfit24` → теперь `POSTGRES_DB` обязателен из env
  - Убран хардкод `CELERY_BROKER_URL` → берётся из env
- ✅ `.env.local` и `.env`: `POSTGRES_DB=eatfit24_dev`, `POSTGRES_USER=eatfit24_dev`
- ✅ `.env.example` (PROD): требует явное указание `POSTGRES_DB`

**Проверка**:
```bash
# DEV
docker compose exec backend python -c "from django.conf import settings; print(settings.DATABASES['default']['NAME'])"
# Expected: eatfit24_dev

# PROD
docker compose exec backend python -c "from django.conf import settings; print(settings.DATABASES['default']['NAME'])"
# Expected: eatfit24_prod (или другое имя из POSTGRES_DB)
```

---

### P0.6: Telegram безопасность ✅

**Требование**:
1. Debug bypass физически выключен в prod
2. Нигде не логируется `initData`/headers

**Выполнено**:
- ✅ **Debug bypass**:
  - `production.py:121`: `WEBAPP_DEBUG_MODE_ENABLED = False` (жёстко задано)
  - `apps/telegram/auth/authentication.py:56-60`: три проверки (DEBUG=True + APP_ENV="dev" + WEBAPP_DEBUG_MODE_ENABLED)
  - Старых флагов `DEBUG_MODE_ENABLED` нет (только в документации)

- ✅ **Утечки initData**:
  - `apps/telegram/auth/services/webapp_auth.py`: только описания ошибок ("initData too long", "No hash"), не сам initData
  - `apps/nutrition/views.py:336-338`: логируется только `'SET'` или `'NOT SET'`, а не сам заголовок
  - В документации есть примеры с логированием, но они не в коде

**Проверка**:
```bash
# PROD: debug mode должен быть выключен
docker compose exec backend python -c "from django.conf import settings; assert not getattr(settings, 'WEBAPP_DEBUG_MODE_ENABLED', False)"
# Expected: no output (assertion passed)

# Попытка auth с X-Debug-Mode в prod должна быть отклонена
curl -H "X-Debug-Mode: true" https://eatfit24.ru/api/telegram/auth/panel/
# Expected: 401/403 (не проходит)
```

---

## ✅ P1: Важные доработки (COMPLETED)

### P1.1: Celery queues — Вариант A (Redis DB index) ✅

**Решение**: Использовать разные Redis DB index для изоляции DEV/PROD.

**Выполнено**:
- ✅ **DEV** (`.env.local`):
  - `CELERY_BROKER_URL=redis://redis:6379/0`
  - `CELERY_RESULT_BACKEND=redis://redis:6379/1`
- ✅ **PROD** (`.env.example`):
  - `CELERY_BROKER_URL=redis://redis:6379/1`
  - `CELERY_RESULT_BACKEND=redis://redis:6379/2`
- ✅ Очереди одинаковые: `ai`, `billing`, `default` (не нужны _dev суффиксы)

**Проверка**:
```bash
# DEV: проверить, что worker подключен к DB 0
docker compose logs celery-worker | grep "Connected to redis://redis:6379/0"

# PROD: проверить, что worker подключен к DB 1
docker compose logs celery-worker | grep "Connected to redis://redis:6379/1"
```

---

### P1.2: Trainer Panel API контракт ✅

**Требование**:
1. `details` не отдаётся без `?include_details=1`
2. Деньги в API - строки (не float)
3. Pagination объект есть

**Проверка выполнена**:
- ✅ **details**: `apps/telegram/trainer_panel/views.py:97-98` - отдаётся только при `include_details=True`
- ✅ **Деньги**: `apps/telegram/trainer_panel/views.py:299-301` - используется `str(revenue["total"])`
- ✅ **Pagination**: `apps/telegram/trainer_panel/views.py:162` - формат `{"items": [...], "pagination": {"limit": ..., "offset": ..., "total": ...}}`

**Проверка API**:
```bash
# Без include_details - details должен отсутствовать
curl -H "X-Telegram-Init-Data: ..." https://eatfit24.ru/api/telegram/panel/applications/
# Expected: items без поля "details"

# С include_details=1 - details присутствует
curl -H "X-Telegram-Init-Data: ..." "https://eatfit24.ru/api/telegram/panel/applications/?include_details=1"
# Expected: items с полем "details"

# Деньги - строки
curl -H "X-Telegram-Init-Data: ..." https://eatfit24.ru/api/telegram/panel/subscribers/
# Expected: "revenue_total": "11988.00" (string, not number)
```

---

## ✅ P2: Billing adapter корректность (COMPLETED)

**Требование**: Проверить обработку `end_date=null`.

**Проверка выполнена**:
- ✅ `apps/telegram/trainer_panel/billing_adapter.py:63-66`: если `end_date=null`, то `status="active"`
- ✅ `apps/telegram/trainer_panel/billing_adapter.py:77`: `is_paid = (plan_type != "free") AND (status == "active")`
- ✅ **Модель БД**: `apps/billing/models.py:165` - `end_date` без `null=True`, значит всегда заполнено

**Вывод**: Логика корректна. `end_date=null` не должен встречаться по схеме БД, но если встретится — будет считаться активной подпиской (разумный fallback).

---

## 🔥 Финальная валидация

### DEV окружение

```bash
# 1. Запуск
cd /path/to/eatfit24
export COMPOSE_PROJECT_NAME=eatfit24_dev
docker compose up -d --build

# 2. Проверка окружения
docker compose exec backend python -c "from django.conf import settings; print(f'APP_ENV={settings.APP_ENV}, DB={settings.DATABASES[\"default\"][\"NAME\"]}')"
# Expected: APP_ENV=dev, DB=eatfit24_dev

# 3. Тесты
docker compose exec backend pytest -v
# Expected: все тесты проходят

# 4. WebApp через tunnel (нужен cloudflared)
cloudflared tunnel --url http://localhost:5173
# Открыть webapp через Telegram, проверить auth

# 5. Trainer Panel
curl -H "X-Telegram-Init-Data: query_id=..." http://localhost:8000/api/telegram/panel/applications/
# Expected: 200 OK, список заявок

# 6. include_details работает
curl "http://localhost:8000/api/telegram/panel/applications/?include_details=1"
# Expected: items содержат "details"
```

---

### PROD guards (должны падать при неправильном конфиге)

```bash
# 1. APP_ENV != prod
APP_ENV=dev docker compose up backend
# Expected: RuntimeError: [SAFETY] APP_ENV must be 'prod' in production, got: 'dev'

# 2. YOOKASSA_MODE != prod
YOOKASSA_MODE=test docker compose up backend
# Expected: RuntimeError: [SAFETY] YOOKASSA_MODE must be 'prod' in production

# 3. DEBUG=True
DEBUG=True docker compose up backend
# Expected: RuntimeError: [SAFETY] DEBUG=True is forbidden in production

# 4. POSTGRES_DB содержит _dev
POSTGRES_DB=eatfit24_dev docker compose up backend
# Expected: RuntimeError: [SAFETY] Forbidden DB name in production: 'eatfit24_dev'

# 5. REDIS_URL отсутствует
unset REDIS_URL && docker compose up backend
# Expected: RuntimeError: [SAFETY] REDIS_URL must be set in production

# 6. CELERY_BROKER_URL отсутствует
unset CELERY_BROKER_URL && docker compose up backend
# Expected: RuntimeError или ошибка подключения

# 7. Успешный запуск с правильным конфигом
APP_ENV=prod \
POSTGRES_DB=eatfit24_prod \
YOOKASSA_MODE=prod \
DEBUG=False \
REDIS_URL=redis://redis:6379/1 \
CELERY_BROKER_URL=redis://redis:6379/1 \
CELERY_RESULT_BACKEND=redis://redis:6379/2 \
docker compose up -d backend
# Expected: успешный старт
```

---

## 📋 Checklist для деплоя

Перед деплоем в PROD проверить:

- [ ] `.env` на сервере содержит `APP_ENV=prod`
- [ ] `.env` содержит `COMPOSE_PROJECT_NAME=eatfit24_prod`
- [ ] `POSTGRES_DB` НЕ содержит `_dev`/`test`/`local`
- [ ] `YOOKASSA_MODE=prod`
- [ ] `DEBUG=False`
- [ ] `REDIS_URL` указан с правильным DB index (1)
- [ ] `CELERY_BROKER_URL` использует DB 1
- [ ] `CELERY_RESULT_BACKEND` использует DB 2
- [ ] `WEBAPP_DEBUG_MODE_ENABLED` отсутствует в `.env` (будет False по умолчанию)
- [ ] `TELEGRAM_ADMINS` содержит корректные ID админов (через запятую)

---

## 🎯 Итоговый статус

| Задача | Статус | Комментарий |
|--------|--------|-------------|
| P0.1: APP_ENV в settings | ✅ | Добавлен во все env файлы, guards используют |
| P0.2: Env переменные к новой схеме | ✅ | REDIS_URL, CELERY_*, YOOKASSA_MODE обязательны в prod |
| P0.3: TELEGRAM_ADMINS = list[int] | ✅ | Все места корректно обрабатывают list |
| P0.4: COMPOSE_PROJECT_NAME | ✅ | Изоляция volumes/networks через PROJECT_NAME |
| P0.5: Изоляция БД | ✅ | Разные имена БД для dev/prod, хардкод убран |
| P0.6: Telegram безопасность | ✅ | Debug bypass выключен, initData не логируется |
| P1.1: Celery queues | ✅ | Разные Redis DB index (0/1 для dev, 1/2 для prod) |
| P1.2: Trainer Panel API | ✅ | details по флагу, деньги строками, pagination есть |
| P2: Billing adapter | ✅ | end_date=null обрабатывается корректно (fallback) |

**Все задачи выполнены!** 🎉

---

## 🛠️ Utility Scripts

Новые скрипты для тестирования изоляции:

### `scripts/test-isolation.sh`
Проверяет физическую изоляцию DEV/PROD:
- Docker projects
- Volumes prefixing
- Networks prefixing
- Containers prefixing
- Database names
- Redis DB indexes

**Usage**:
```bash
./scripts/test-isolation.sh
```

### `scripts/test-prod-guards.sh`
Тестирует PROD guards (fail-fast):
- APP_ENV != prod → должен падать
- DEBUG=True → должен падать
- YOOKASSA_MODE != prod → должен падать
- POSTGRES_DB содержит _dev → должен падать
- REDIS_URL отсутствует → должен падать
- Test YooKassa key → должен падать

**Usage**:
```bash
./scripts/test-prod-guards.sh
```

---

## 📚 Дополнительные ссылки

- [CLAUDE.md](CLAUDE.md) - инструкции для Claude Code
- [backend/config/settings/production.py](backend/config/settings/production.py) - PROD guards
- [backend/config/settings/local.py](backend/config/settings/local.py) - DEV настройки
- [compose.yml](compose.yml) - Docker Compose конфигурация (с изоляцией)
- [.env.example](.env.example) - пример PROD env файла
- [.env.local](.env.local) - пример DEV env файла
- [scripts/test-isolation.sh](scripts/test-isolation.sh) - скрипт тестирования изоляции
- [scripts/test-prod-guards.sh](scripts/test-prod-guards.sh) - скрипт тестирования guards
