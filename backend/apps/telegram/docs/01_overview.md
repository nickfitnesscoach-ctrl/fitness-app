# Telegram-домен: Обзор

| | |
|---|---|
| **Статус** | production-ready |
| **Владелец** | `apps/telegram/` |
| **Проверено** | 2024-12-16 |
| **Правило** | Меняешь код в `apps/telegram/*` → обнови docs |

---

## Где НЕ искать код (Quick Reference)

| Нужен код для... | Смотри в... |
|------------------|-------------|
| Подписки, платежи, биллинг | `apps/billing/` |
| КБЖУ, еда, дневник | `apps/nutrition/` |
| Профиль пользователя | `apps/users/` |
| AI-генерация планов | `apps/ai/`, `apps/ai_proxy/` |
| **Telegram-интеграция** | `apps/telegram/` ← ты здесь |

---

## Назначение

Telegram-домен (`apps/telegram/`) — это интеграционный слой между Telegram-экосистемой и основным бэкендом приложения EatFit24. Он отвечает за:

1. **Аутентификацию пользователей** через Telegram Mini App (WebApp)
2. **Лид-магнит** — сбор данных через Telegram-бота (AI-тест)
3. **Панель тренера** — административный интерфейс для управления клиентами

---

## Три роли Telegram в проекте

### 1. Вход пользователей

Telegram является **единственным способом аутентификации** для обычных пользователей. Вместо классической пары логин/пароль используется подпись `initData` от Telegram WebApp.

**Как это работает:**
- Пользователь открывает Mini App внутри Telegram
- Telegram автоматически передаёт подписанные данные (`initData`)
- Backend проверяет подпись и создаёт/авторизует пользователя

### 2. Лид-магнит (Telegram Bot)

Бот — это точка входа новых пользователей. Он:
- Проводит AI-тест (анкетирование)
- Сохраняет ответы пользователя через Bot API
- Рассчитывает рекомендации по КБЖУ
- Генерирует персональные планы через AI

**Важно:** Бот общается с backend через отдельный API, защищённый секретным ключом (`X-Bot-Secret`), а не через Telegram initData.

### 3. Панель тренера (Trainer Panel)

Административный интерфейс для тренера/владельца бизнеса:
- Просмотр заявок (кто прошёл тест)
- Управление клиентами
- Статистика подписок и выручки

Trainer Panel — это **тоже Telegram WebApp**, но с проверкой прав администратора.

---

## Интерфейсы Telegram-домена

| Интерфейс | Кто использует | Аутентификация | Где код |
|-----------|----------------|----------------|---------|
| **Telegram Mini App Auth** | Обычные пользователи | `initData` подпись | `auth/` |
| **Bot API** | Telegram-бот | `X-Bot-Secret` заголовок | `bot/` |
| **Trainer Panel API** | Администраторы | `initData` + проверка `TELEGRAM_ADMINS` | `trainer_panel/` |

---

## Что НЕ является частью Telegram-домена

> [!IMPORTANT]
> Чёткое понимание границ — ключ к корректной работе с кодом.

### НЕ входит в `apps/telegram/`:

| Функционал | Где живёт | Связь с Telegram |
|------------|-----------|------------------|
| **Billing** (оплаты, подписки) | `apps/billing/` | Telegram обращается через `billing_adapter` |
| **Nutrition** (еда, калории, дневник) | `apps/nutrition/` | Данные КБЖУ копируются в TelegramUser |
| **AI/ML логика** | `apps/ai/`, `apps/ai_proxy/` | Telegram лишь триггерит генерацию |
| **Профиль пользователя** | `apps/users/` | TelegramUser ссылается на Django User/Profile |
| **Frontend** (Mini App, Trainer Panel UI) | `frontend/` | Использует API из этого домена |

### Граница ответственности

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (WebApp)                        │
│    • Mini App UI                                                 │
│    • Trainer Panel UI                                            │
└─────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                apps/telegram/ (ЭТОТ ДОМЕН)                       │
│                                                                  │
│    ┌──────────┐    ┌──────────┐    ┌────────────────┐           │
│    │   auth/  │    │   bot/   │    │ trainer_panel/ │           │
│    └──────────┘    └──────────┘    └────────────────┘           │
│         │               │                  │                     │
│    • initData      • X-Bot-Secret     • Admin check             │
│    • JWT tokens    • Save test        • Applications            │
│    • User create   • Create plan      • Clients                 │
│                                       • Subscribers              │
└─────────────────────────────────────────────────────────────────┘
                               │
           ┌───────────────────┼───────────────────┐
           ▼                   ▼                   ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │ apps/users/  │   │apps/billing/ │   │apps/nutrition│
    │              │   │              │   │              │
    │ • Profile    │   │ • Payments   │   │ • DailyGoal  │
    │ • Django User│   │ • Subscript. │   │ • Meals      │
    └──────────────┘   └──────────────┘   └──────────────┘
```

---

## Модели данных (кратко)

Telegram-домен владеет тремя моделями:

| Модель | Назначение | Связи |
|--------|------------|-------|
| `TelegramUser` | Профиль Telegram-пользователя | OneToOne → Django User |
| `PersonalPlanSurvey` | Анкета перед генерацией плана | ForeignKey → User |
| `PersonalPlan` | Сгенерированный AI-план | ForeignKey → User, Survey |

Подробности см. в [06_models_and_data.md](./06_models_and_data.md).

---

## Ключевые принципы

### 1. SSOT (Single Source of Truth)

- **Django User** — центральная сущность пользователя
- **TelegramUser** — расширение User данными из Telegram
- **Profile** (из `apps/users/`) — пользовательские настройки

### 2. Безопасность по умолчанию

- В PROD debug-режимы **отключены**
- Bot API требует секрет (`X-Bot-Secret`)
- Trainer Panel требует проверки `TELEGRAM_ADMINS`
- initData проверяется криптографически

### 3. Изоляция от billing

Telegram-домен **не лезет** напрямую в модели `apps/billing/`. Вся работа с подписками идёт через `billing_adapter.py`, который:
- Возвращает данные в формате, удобном для панели
- Обеспечивает отсутствие N+1 запросов
- Изолирует изменения в billing от Telegram-кода

---

## API Endpoints (сводка)

### Аутентификация (`/api/v1/telegram/`)

| Endpoint | Метод | Описание |
|----------|-------|----------|
| `/auth/` | POST | Основная авторизация Mini App → JWT |
| `/webapp/auth/` | POST | Универсальная авторизация (с profile/goals) |
| `/trainer/admin-panel/` | POST | Авторизация Trainer Panel |
| `/profile/` | GET | Профиль текущего пользователя (JWT) |

### Bot API (`/api/v1/telegram/`)

| Endpoint | Метод | Защита | Описание |
|----------|-------|--------|----------|
| `/save-test/` | POST | X-Bot-Secret | Сохранение результатов AI-теста |
| `/users/get-or-create/` | GET | X-Bot-Secret | Получить/создать пользователя |
| `/personal-plan/survey/` | POST | X-Bot-Secret | Создать анкету |
| `/personal-plan/plan/` | POST | X-Bot-Secret | Создать AI-план |
| `/personal-plan/count-today/` | GET | X-Bot-Secret | Счётчик планов за день |
| `/invite-link/` | GET | — | Ссылка на бота (публичный) |

### Trainer Panel (`/api/v1/telegram/`)

| Endpoint | Метод | Защита | Описание |
|----------|-------|--------|----------|
| `/applications/` | GET | TelegramAdminPermission | Список заявок |
| `/clients/` | GET/POST | TelegramAdminPermission | Список/добавление клиентов |
| `/clients/{id}/` | DELETE | TelegramAdminPermission | Удаление из клиентов |
| `/subscribers/` | GET | TelegramAdminPermission | Статистика подписок/выручки |

---

## Следующие шаги

- [02_architecture.md](./02_architecture.md) — устройство папок и архитектура
- [03_auth_and_security.md](./03_auth_and_security.md) — критически важно для безопасности
- [04_bot_api.md](./04_bot_api.md) — документация Bot API
- [05_trainer_panel.md](./05_trainer_panel.md) — документация Trainer Panel
- [06_models_and_data.md](./06_models_and_data.md) — модели данных
