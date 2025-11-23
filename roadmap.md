# Roadmap: Fitness-App (FoodMind) - Фиксы и ревью монорепы

> **Дата создания:** 2025-11-23
> **Продакшн домен:** https://eatfit24.ru
> **Статус:** P0 выполнен ✅

---

## Оглавление

1. [Обзор состояния проекта](#1-обзор-состояния-проекта)
2. [P0: Critical Bug - Failed to update goals](#2-p0-critical-bug---failed-to-update-goals)
3. [Backend: Задачи и фиксы](#3-backend-задачи-и-фиксы)
4. [Bot: Задачи и фиксы](#4-bot-задачи-и-фиксы)
5. [Frontend: Задачи и фиксы](#5-frontend-задачи-и-фиксы)
6. [Infrastructure: Docker и CI/CD](#6-infrastructure-docker-и-cicd)
7. [Приоритизация всех задач](#7-приоритизация-всех-задач)
8. [Порядок выполнения работ](#8-порядок-выполнения-работ)

---

## 1. Обзор состояния проекта

### Архитектура

Монорепа fitness-app (FoodMind) состоит из трех сервисов:

- **Backend** (`backend/`) — Django 5.x + DRF + PostgreSQL 15
- **Bot** (`bot/`) — Telegram-бот на aiogram 3.x + SQLAlchemy + Alembic
- **Frontend** (`frontend/`) — Vite 7.x + React 19.x + TailwindCSS

Сервисы связаны через:
- Единую PostgreSQL базу данных
- REST API (`/api/v1/*`)
- Docker Compose сеть `backend-net`

### Диаграмма взаимодействия

```
┌─────────────────────┐        ┌─────────────────────┐
│   TELEGRAM USER     │        │   TELEGRAM USER     │
│  (Telegram App)     │        │  (WebApp Browser)   │
└─────────┬───────────┘        └─────────┬───────────┘
          │                              │
          ▼                              ▼
┌─────────────────────┐        ┌─────────────────────┐
│       BOT           │        │     FRONTEND        │
│  (aiogram 3.x)      │        │  (React/Vite)       │
│                     │        │                     │
│ POST /telegram/     │        │ PUT /nutrition/     │
│      save-test/     │        │     goals/          │
└─────────┬───────────┘        └─────────┬───────────┘
          │                              │
          └──────────────┬───────────────┘
                         ▼
              ┌─────────────────────┐
              │      BACKEND        │
              │  (Django/DRF)       │
              │                     │
              │  TelegramHeader     │
              │  Authentication     │
              └─────────┬───────────┘
                        │
                        ▼
              ┌─────────────────────┐
              │    POSTGRESQL       │
              │    (postgres:15)    │
              └─────────────────────┘
```

### Общая оценка

| Компонент | Статус | Оценка |
|-----------|--------|--------|
| Backend конфигурация | ⚠️ Требует внимания | 5/10 |
| Backend API | ✅ Хорошо | 7/10 |
| Backend безопасность | ❌ Критические проблемы | 4/10 |
| Bot логика | ✅ Хорошо | 8/10 |
| Bot интеграция с Django | ⚠️ Требует внимания | 6/10 |
| Frontend API интеграция | ❌ Критические проблемы | 4/10 |
| Frontend Telegram WebApp | ⚠️ Требует внимания | 6/10 |
| Docker/Compose | ⚠️ Требует внимания | 6/10 |
| CI/CD | ❌ Критические проблемы | 4/10 |

**Главный блокер:** Ошибка "Failed to update goals Telegram ID: 310151740" в WebApp на вкладке "Мои цели".

---

## 2. P0: Critical Bug - Failed to update goals

### Описание проблемы

При попытке обновить дневные цели (КБЖУ) в Telegram WebApp пользователь видит:
```
Failed to update goals Telegram ID: 310151740
```

### Анализ цепочки вызовов

#### Frontend (ProfilePage.tsx → api.ts)

```typescript
// frontend/src/pages/ProfilePage.tsx:93-134
const handleSaveGoals = async () => {
    await api.updateGoals(editedGoals);
}

// frontend/src/services/api.ts:407-445
async updateGoals(data: any) {
    const response = await fetch('/api/v1/nutrition/goals/', {
        method: 'PUT',
        headers: {
            'X-Telegram-ID': telegramId,      // ← Отправляет
            'X-TG-INIT-DATA': telegramInitData // ← Отправляет
        },
        body: JSON.stringify({...})
    });
}
```

#### Backend (urls.py → views.py)

```python
# backend/apps/nutrition/urls.py:33
path('nutrition/goals/', views.DailyGoalView.as_view(), name='daily-goal')

# backend/apps/nutrition/views.py:313-383
class DailyGoalView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]

    def put(self, request, *args, **kwargs):
        obj = self.get_object()  # DailyGoal.objects.get(user=request.user, is_active=True)
        if obj is None:
            serializer.save()  # ← Проблема: user не передается явно
```

### Гипотезы причины ошибки

1. **URL маршрут дублируется** — `/api/v1/nutrition/goals/` в urlpatterns указан как `nutrition/goals/`, что создает путь `/api/v1/nutrition/nutrition/goals/`

2. **Несоответствие аутентификации** — Frontend отправляет `X-Telegram-ID` header, но view использует `IsAuthenticated` (JWT), а не `TelegramHeaderAuthentication`

3. **Отсутствует Profile при создании TelegramUser** — При первом логине создается User без связанного Profile, что требуется для расчета целей

4. **Отсутствует обработка ошибок** — В `DailyGoalView.put()` нет try-catch при создании новой цели

### Файлы для исправления

| Файл | Строки | Проблема |
|------|--------|----------|
| `backend/apps/nutrition/urls.py` | 33 | URL паттерн `nutrition/goals/` → должен быть `goals/` |
| `backend/apps/nutrition/views.py` | 355-362 | Нет try-catch, user не передается в serializer.save() |
| `backend/apps/telegram/authentication.py` | 285-315 | При создании User не создается Profile |
| `backend/config/settings/base.py` | 208-211 | Проверить порядок authentication classes |

### Шаги фикса (P0)

```
P0-1: ✅ DONE - Проверить и исправить URL паттерн в nutrition/urls.py
      - Изменить path('nutrition/goals/', ...) на path('goals/', ...)
      - Проверить что итоговый URL = /api/v1/nutrition/goals/

P0-2: ✅ DONE - Добавить обработку ошибок в DailyGoalView.put()
      - Обернуть serializer.save() в try-catch
      - Добавлено логирование request.user и request.data

P0-3: ✅ DONE - Создавать Profile при первом логине через Telegram
      - В TelegramHeaderAuthentication._create_telegram_user()
      - Добавлен Profile.objects.get_or_create(user=user)

P0-4: ✅ DONE - Добавить логирование для диагностики
      - В DailyGoalView.put() логирование request.user и request.data
      - В TelegramHeaderAuthentication логирование ошибок Profile
```

### Приоритет: **P0 — БЛОКЕР**
### Сложность: **Средняя**
### Оценка времени: 2-4 часа

---

## 3. Backend: Задачи и фиксы

### B1 | P1 | ✅ DONE | Удалить реальные секреты из .env и кода

**Проблема:** Файл `.env` содержит реальные API ключи (OpenRouter, Telegram Bot Token, YooKassa). В `urls.py` хардкодный пароль для Swagger (admin/2865).

**Файлы:**
- `backend/.env`
- `backend/config/urls.py` (строки 23-24)

**Действия:**
- ✅ `.env.example` обновлён с placeholders и SWAGGER_AUTH_* переменными
- ⚠️ Ротировать все скомпрометированные ключи (вручную в консолях сервисов)
- ⚠️ Удалить `.env` из Git истории (BFG Repo-Cleaner) — если был закоммичен

**Сложность:** Средняя

---

### B2 | P1 | ✅ DONE | Заменить hardcoded Basic Auth для Swagger

**Проблема:** Swagger UI защищен Basic Auth с хардкодным паролем "2865".

**Файлы:**
- `backend/config/urls.py` (строки 19-52, 71-73)

**Действия:**
- ✅ Credentials вынесены в env переменные (SWAGGER_AUTH_USERNAME, SWAGGER_AUTH_PASSWORD)
- ✅ В DEBUG режиме без пароля — доступ разрешён
- ✅ В production без пароля — доступ запрещён

**Сложность:** Низкая

---

### B3 | P1 | ✅ DONE | Исправить ALLOWED_HOSTS в production.py

**Проблема:** При пустой переменной `ALLOWED_HOSTS` используется `["*"]` — уязвимость Host Header Injection.

**Файлы:**
- `backend/config/settings/production.py` (строка 12)

**Действия:**
- ✅ Изменён default: теперь пустой список вместо `["*"]`
- ✅ Добавлена проверка при старте: `raise ValueError` если не задан

**Сложность:** Низкая

---

### B4 | P2 | ✅ DONE | Объединить prod.py и production.py

**Проблема:** Два файла конфигурации для production с разными настройками.

**Файлы:**
- `backend/config/settings/prod.py` (удалён)
- `backend/config/settings/production.py`

**Действия:**
- ✅ Удалён устаревший `prod.py` (использовал DATABASE_URL)
- ✅ Оставлен `production.py` с Security Headers и POSTGRES_* переменными

**Сложность:** Средняя

---

### B5 | P2 | ✅ DONE | Унифицировать переменные окружения БД

**Проблема:** В разных конфигах используются `POSTGRES_*`, `DB_*`, `DATABASE_URL`.

**Файлы:**
- `backend/.env.example`

**Действия:**
- ✅ Стандартизированы на `POSTGRES_*` (используется везде)
- ✅ Удалены дубли: `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`
- ✅ Обновлён `.env.example`

**Сложность:** Средняя

---

### B6 | P2 | ✅ DONE | Добавить Security Headers

**Проблема:** Отсутствуют HSTS, CSP и другие security headers.

**Файлы:**
- `backend/config/settings/production.py`

**Действия:**
- ✅ SECURE_HSTS_SECONDS = 31536000 (1 year)
- ✅ SECURE_HSTS_INCLUDE_SUBDOMAINS = True
- ✅ SECURE_HSTS_PRELOAD = True
- ✅ SECURE_CONTENT_TYPE_NOSNIFF = True
- ✅ SECURE_BROWSER_XSS_FILTER = True
- ✅ X_FRAME_OPTIONS = "DENY"
- ✅ SECURE_SSL_REDIRECT (configurable via env)

**Сложность:** Низкая

---

### B7 | P2 | ✅ DONE | Исправить settings import в wsgi/asgi

**Проблема:** Хардкод `config.settings.local` в production.

**Файлы:**
- `backend/config/wsgi.py`
- `backend/config/asgi.py`

**Действия:**
- ✅ Изменён default на `config.settings.production` в wsgi.py
- ✅ Изменён default на `config.settings.production` в asgi.py

**Сложность:** Низкая

---

### B8 | P3 | Убрать DEBUG из health endpoint

**Проблема:** `/health/` возвращает `debug: true/false` — раскрытие информации.

**Файлы:**
- `backend/apps/common/views.py` (строка 29)

**Сложность:** Низкая

---

### B9 | P3 | Перенести TELEGRAM_ADMINS в env

**Проблема:** Хардкод `{310151740}` в коде.

**Файлы:**
- `backend/config/settings/base.py` (строка 521)

**Сложность:** Низкая

---

### B10 | P3 | Исправить CORS validation

**Проблема:** Закомментирована проверка пустого `CORS_ALLOWED_ORIGINS`.

**Файлы:**
- `backend/config/settings/base.py` (строки 409-414)

**Сложность:** Низкая

---

## 4. Bot: Задачи и фиксы

### T1 | P1 | ✅ DONE | Добавить retry логику для Django API

**Проблема:** Нет retry при отправке данных в Django. Одна ошибка сети = потеря данных пользователя.

**Файлы:**
- `bot/app/services/django_integration.py`
- `bot/app/config.py`

**Действия:**
- ✅ Использовать tenacity с exponential backoff
- ✅ Retry на 429, 502, 503, 504
- ✅ Максимум 3 попытки (настраивается через env)

**Сложность:** Средняя

---

### T2 | P1 | ✅ DONE | Добавить обработку ошибок миграций в Dockerfile

**Проблема:** `alembic upgrade head` в CMD — при ошибке контейнер падает.

**Файлы:**
- `bot/Dockerfile`
- `bot/entrypoint.sh` (создан)

**Действия:**
- ✅ Создать `entrypoint.sh`
- ✅ Добавить ожидание БД (pg_isready)
- ✅ Добавить проверку статуса миграций (продолжает работу при ошибке)
- ✅ Логировать результат

**Сложность:** Средняя

---

### T3 | P1 | ✅ DONE | Удалить дублирование функции confirm_and_generate

**Проблема:** Функция определена в двух местах.

**Файлы:**
- `bot/app/handlers/survey/confirmation.py` (оставлена)
- `bot/app/handlers/personal_plan.py` (удалён)

**Действия:**
- ✅ Удалён устаревший `personal_plan.py` (990 строк)
- ✅ Оставлена модульная структура в `survey/`

**Сложность:** Средняя

---

### T4 | P2 | ✅ DONE | Исправить bare except clause

**Проблема:** `except:` скрывает неожиданные ошибки.

**Файлы:**
- `bot/app/services/django_integration.py`

**Действия:**
- ✅ Заменено `except:` на `except (ValueError, TypeError):` в функции parse_range_value

**Сложность:** Низкая

---

### T5 | P2 | Добавить валидацию схемы Django API

**Проблема:** Нет валидации payload перед отправкой в Django.

**Файлы:**
- `bot/app/services/django_integration.py`

**Действия:**
- Создать Pydantic модель для payload
- Валидировать перед отправкой

**Сложность:** Средняя

---

### T6 | P2 | ✅ DONE | Сделать timeout конфигурируемым

**Проблема:** Timeout жестко установлен в 10 секунд.

**Файлы:**
- `bot/app/config.py`
- `bot/app/services/django_integration.py`

**Действия:**
- ✅ Добавлен `DJANGO_API_TIMEOUT` в config.py (default 30 секунд)
- ✅ Заменён hardcoded timeout на `settings.DJANGO_API_TIMEOUT`

**Сложность:** Низкая

---

### T7 | P3 | Добавить healthcheck для Django API

**Проблема:** Нет проверки доступности Django.

**Файлы:**
- `bot/app/services/django_integration.py`

**Сложность:** Средняя

---

## 5. Frontend: Задачи и фиксы

### F1 | P1 | ✅ DONE | Ревизия auth - только Header Auth для WebApp

**Проблема:** Frontend смешивал JWT и Header auth механизмы.

**Файлы:**
- `frontend/src/lib/telegram.ts` — централизованный модуль Telegram WebApp
- `frontend/src/services/api.ts` — API клиент
- `frontend/src/contexts/AuthContext.tsx` — auth state management

**Действия:**
- ✅ Создан централизованный `buildTelegramHeaders()` в `telegram.ts`
- ✅ API клиент использует только Header Auth (X-Telegram-ID, X-Telegram-Init-Data и др.)
- ✅ JWT методы оставлены как deprecated no-op для совместимости
- ✅ AuthContext использует async init и exposes `telegramUser`, `isInitialized`

**Сложность:** Высокая

---

### F2 | P1 | ✅ DONE | Централизовать API URL через VITE_API_URL

**Проблема:** API URL был hardcoded в разных местах.

**Файлы:**
- `frontend/src/services/api.ts`
- `frontend/.env.example`

**Действия:**
- ✅ `API_BASE = import.meta.env.VITE_API_URL || '/api/v1'`
- ✅ Создан объект `URLS` с всеми endpoint путями
- ✅ Все fetch используют централизованные URLS
- ✅ Обновлён `.env.example` с примерами для prod/dev

**Сложность:** Средняя

---

### F3 | P1 | ✅ DONE | Гарантировать Telegram init перед API запросами

**Проблема:** API запросы могли выполняться до инициализации Telegram WebApp.

**Файлы:**
- `frontend/src/lib/telegram.ts`
- `frontend/src/contexts/AuthContext.tsx`

**Действия:**
- ✅ Async `initTelegramWebApp()` с singleton pattern и кэшированием
- ✅ AuthContext вызывает `initTelegramWebApp()` первым шагом
- ✅ `buildTelegramHeaders()` возвращает graceful fallback если не инициализировано
- ✅ DEV режим через VITE_SKIP_TG_AUTH с фейковыми данными

**Сложность:** Средняя

---

### F4 | P2 | Добавить универсальный error handling

**Проблема:** Inconsistent обработка ошибок, нет retry логики.

**Файлы:**
- `frontend/src/services/api.ts`

**Действия:**
- Создать error middleware
- Добавить retry с exponential backoff
- Унифицировать формат ошибок

**Сложность:** Средняя

---

### F5 | P2 | ✅ DONE | Добавить timeout для fetch запросов

**Проблема:** Все fetch без timeout — могут зависать.

**Файлы:**
- `frontend/src/services/api.ts`

**Действия:**
- ✅ Создана функция `fetchWithTimeout()` с AbortController
- ✅ Все 21 вызов `fetch` заменены на `fetchWithTimeout`
- ✅ Timeout по умолчанию 30 секунд (API_TIMEOUT)

**Сложность:** Низкая

---

### F6 | P2 | Создать единую обработку ошибок в компонентах

**Проблема:** ApplicationsPage не обрабатывает ошибки, разный подход в разных компонентах.

**Файлы:**
- `frontend/src/pages/ApplicationsPage.tsx`
- `frontend/src/contexts/ClientsContext.tsx`

**Действия:**
- Показывать ошибки через Telegram alerts
- Единый error boundary

**Сложность:** Средняя

---

### F7 | P3 | Разделить dev/prod конфигурацию

**Проблема:** `VITE_SKIP_TG_AUTH` перемешан с production кодом.

**Файлы:**
- `frontend/.env.example`
- `frontend/vite.config.ts`

**Сложность:** Низкая

---

### F8 | P3 | Добавить image placeholder

**Проблема:** Нет обработки broken images для photo_url.

**Файлы:**
- `frontend/src/pages/ApplicationsPage.tsx`
- `frontend/src/pages/ClientsPage.tsx`

**Сложность:** Низкая

---

## 6. Infrastructure: Docker и CI/CD

### D1 | P1 | ✅ DONE | Добавить healthchecks для Bot и Frontend

**Проблема:** Нет healthchecks — невозможно управлять lifecycle.

**Файлы:**
- `docker-compose.yml`

**Действия:**
- ✅ Добавлен healthcheck для frontend (`curl -f http://localhost:80/`)
- ✅ Bot использует entrypoint.sh с pg_isready

**Сложность:** Низкая

---

### D2 | P1 | ✅ DONE | Перенести миграции в ENTRYPOINT

**Проблема:** Миграции в docker-compose CMD — не переиспользуемо.

**Файлы:**
- `backend/Dockerfile`
- `backend/entrypoint.sh` (создан)
- `bot/entrypoint.sh` (создан ранее)
- `docker-compose.yml`

**Действия:**
- ✅ Создан `entrypoint.sh` для backend (DB wait, migrate, collectstatic, gunicorn)
- ✅ Bot entrypoint уже создан ранее
- ✅ Убрана команда из docker-compose.yml для backend
- ✅ Dockerfile использует ENTRYPOINT вместо CMD

**Сложность:** Средняя

---

### D3 | P1 | ✅ DONE | Удалить hardcoded пароли из defaults

**Проблема:** `POSTGRES_PASSWORD=supersecret` в defaults.

**Файлы:**
- `docker-compose.yml`

**Действия:**
- ✅ Заменено `${POSTGRES_PASSWORD:-supersecret}` на `${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}`
- ✅ Добавлен комментарий о необходимости .env файла

**Сложность:** Низкая

---

### D4 | P1 | ✅ DONE | Сделать тесты обязательными в CI/CD

**Проблема:** `continue-on-error: true` — тесты не блокируют deploy.

**Файлы:**
- `.github/workflows/bot.yml`

**Действия:**
- ✅ Удалён `continue-on-error: true` для lint и formatting
- ✅ Удалён `|| echo` fallback для pytest
- ✅ Backend workflow уже был корректно настроен (needs: build-test)

**Сложность:** Низкая

---

### D5 | P1 | ✅ DONE | Добавить service_healthy условия

**Проблема:** Bot и Frontend зависят от Backend без проверки здоровья.

**Файлы:**
- `docker-compose.yml`

**Действия:**
- ✅ Bot: `depends_on: db: service_healthy, backend: service_healthy`
- ✅ Frontend: `depends_on: backend: service_healthy`

**Сложность:** Низкая

---

### D6 | P1 | ✅ DONE | Убрать hardcoded IP из nginx.conf

**Проблема:** `proxy_pass http://85.198.81.133:8000` — хардкод IP.

**Файлы:**
- `frontend/nginx.conf`

**Действия:**
- ✅ Заменено на `http://backend:8000/api/`
- ✅ Добавлена передача Telegram auth headers через nginx

**Сложность:** Низкая

---

### D7 | P2 | Добавить Frontend тесты в CI/CD

**Проблема:** Нет тестов, линтинга, проверки типов.

**Файлы:**
- `.github/workflows/frontend.yml`

**Действия:**
- Добавить `npm test`
- Добавить `npm run lint`
- Добавить `npm run type-check`

**Сложность:** Средняя

---

### D8 | P2 | Создать ENTRYPOINT скрипты

**Проблема:** Нет ENTRYPOINT для управления startup.

**Файлы:**
- `backend/entrypoint.sh` (создать)
- `bot/entrypoint.sh` (создать)

**Сложность:** Средняя

---

### D9 | P2 | ✅ DONE | Multi-stage build для Backend

**Проблема:** Образ содержит dev зависимости (pip, gcc).

**Файлы:**
- `backend/Dockerfile`

**Действия:**
- ✅ Stage 1 (builder): Компиляция зависимостей с gcc
- ✅ Stage 2 (runtime): Только Python runtime + postgresql-client + libpq5
- ✅ Копирование compiled packages из builder
- ✅ Уменьшение размера образа (~30-40% экономии)

**Сложность:** Средняя

---

### D10 | P3 | Добавить rollback механизм

**Проблема:** При падении deploy нет способа откатиться.

**Файлы:**
- `.github/workflows/*.yml`

**Сложность:** Высокая

---

### D11 | P3 | Добавить secrets валидацию

**Проблема:** Secrets используются без проверки наличия.

**Файлы:**
- `.github/workflows/*.yml`

**Сложность:** Низкая

---

## 7. Приоритизация всех задач

### P0 — Блокеры (должны быть исправлены немедленно)

| ID | Компонент | Описание | Сложность |
|----|-----------|----------|-----------|
| P0-1 | Backend | Исправить URL паттерн `/nutrition/goals/` | Низкая |
| P0-2 | Backend | Добавить обработку ошибок в DailyGoalView | Средняя |
| P0-3 | Backend | Создавать Profile при первом Telegram логине | Средняя |

### P1 — Критично для стабильного продакшна

| ID | Компонент | Описание | Сложность |
|----|-----------|----------|-----------|
| B1 | Backend | Удалить секреты из кода и .env | Средняя |
| B2 | Backend | Заменить hardcoded Basic Auth | Низкая |
| B3 | Backend | Исправить ALLOWED_HOSTS | Низкая |
| T1 | Bot | Добавить retry для Django API | Средняя |
| T2 | Bot | Обработка ошибок миграций в Dockerfile | Средняя |
| T3 | Bot | Удалить дублирование confirm_and_generate | Средняя |
| F1 | Frontend | Исправить Authentication механизм | Высокая |
| F2 | Frontend | Централизовать API URL | Средняя |
| F3 | Frontend | Гарантировать инициализацию Telegram | Средняя |
| D1 | Infra | Healthchecks для Bot/Frontend | Низкая |
| D2 | Infra | Миграции в ENTRYPOINT | Средняя |
| D3 | Infra | Удалить hardcoded пароли | Низкая |
| D4 | Infra | Тесты обязательны в CI/CD | Низкая |
| D5 | Infra | service_healthy условия | Низкая |
| D6 | Infra | Убрать hardcoded IP | Низкая |

### P2 — Важно, но после запуска

| ID | Компонент | Описание | Сложность |
|----|-----------|----------|-----------|
| B4 | Backend | Объединить prod.py/production.py | Средняя |
| B5 | Backend | Унифицировать env переменные БД | Средняя |
| B6 | Backend | Добавить Security Headers | Низкая |
| B7 | Backend | Исправить wsgi/asgi import | Низкая |
| T4 | Bot | Исправить bare except | Низкая |
| T5 | Bot | Валидация схемы Django API | Средняя |
| T6 | Bot | Конфигурируемый timeout | Низкая |
| F4 | Frontend | Универсальный error handling | Средняя |
| F5 | Frontend | Timeout для fetch | Низкая |
| F6 | Frontend | Единая обработка ошибок в компонентах | Средняя |
| D7 | Infra | Frontend тесты в CI/CD | Средняя |
| D8 | Infra | ENTRYPOINT скрипты | Средняя |
| D9 | Infra | Multi-stage build Backend | Средняя |

### P3 — Nice-to-have

| ID | Компонент | Описание | Сложность |
|----|-----------|----------|-----------|
| B8 | Backend | Убрать DEBUG из health | Низкая |
| B9 | Backend | TELEGRAM_ADMINS в env | Низкая |
| B10 | Backend | CORS validation | Низкая |
| T7 | Bot | Healthcheck для Django API | Средняя |
| F7 | Frontend | Разделить dev/prod конфиг | Низкая |
| F8 | Frontend | Image placeholder | Низкая |
| D10 | Infra | Rollback механизм | Высокая |
| D11 | Infra | Secrets валидация | Низкая |

---

## 8. Порядок выполнения работ

### Фаза 1: Критический баг (P0) — День 1

```
Шаг 1: P0-1 → P0-2 → P0-3 (последовательно)
       - Исправить URL
       - Добавить error handling
       - Создавать Profile

Шаг 2: Тестирование в dev окружении
       - Проверить PUT /api/v1/nutrition/goals/
       - Убедиться что цели обновляются
```

### Фаза 2: Безопасность (P1 Security) — День 2

```
Шаг 1: B1 (ротация секретов) — СРОЧНО
Шаг 2: B2, B3 (hardcoded auth, ALLOWED_HOSTS) — параллельно
Шаг 3: D3, D6 (hardcoded пароли и IP) — параллельно
```

### Фаза 3: Frontend аутентификация (P1) — День 3-4

```
Шаг 1: F1 (исправить auth механизм)
Шаг 2: F2, F3 (API URL, Telegram init) — параллельно
Шаг 3: Тестирование всех API вызовов из WebApp
```

### Фаза 4: Bot и Infra (P1) — День 5-6

```
Шаг 1: T1, T2, T3 (retry, миграции, дублирование)
Шаг 2: D1, D2, D4, D5 (healthchecks, entrypoint, CI/CD)
Шаг 3: Полный deploy и smoke test
```

### Фаза 5: Стабилизация (P2) — Неделя 2

```
Можно делать параллельно:
- B4, B5, B6, B7 (Backend cleanup)
- T4, T5, T6 (Bot improvements)
- F4, F5, F6 (Frontend error handling)
- D7, D8, D9 (CI/CD improvements)
```

### Фаза 6: Улучшения (P3) — По мере времени

```
Nice-to-have задачи можно делать в любом порядке
```

### После каких шагов можно безопасно выходить в прод

1. **Минимальный MVP:** После Фазы 1 (P0 исправлен)
   - WebApp работает
   - Цели обновляются
   - ⚠️ Риски безопасности остаются

2. **Безопасный production:** После Фазы 2 + Фазы 3
   - Секреты ротированы
   - Auth работает корректно
   - ⚠️ Bot может терять данные при ошибках

3. **Стабильный production:** После Фазы 4
   - Все P1 задачи выполнены
   - Healthchecks работают
   - CI/CD блокирует плохой код
   - ✅ Рекомендуемая точка для production

---

## Примечание

> **На этом этапе никаких правок в код не вносилось.**
> Патчи и диффы будут делаться отдельными запросами по группам задач.

---

*Документ создан автоматически на основе анализа монорепы fitness-app*
