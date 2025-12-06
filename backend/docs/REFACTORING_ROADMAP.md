# Анализ Django Backend - FoodMind AI
# Refactoring Roadmap

**Дата создания:** 2025-12-06  
**Версия:** 1.0

---

## 1. Архитектура проекта

### Структура приложений (apps)

| App | Назначение | Модели | Ключевые файлы |
|-----|-----------|--------|----------------|
| **users** | Авторизация, профили | `Profile`, `EmailVerificationToken` | views, serializers, services, validators, throttles |
| **nutrition** | Дневник питания, КБЖУ | `Meal`, `FoodItem`, `DailyGoal` | views, serializers |
| **billing** | Подписки, платежи | `SubscriptionPlan`, `Subscription`, `Payment`, `Refund` | views, serializers, services, yookassa_client, usage |
| **ai** | Фото-распознавание | - | views, serializers, throttles |
| **ai_proxy** | Прокси к внешнему AI | - | client, service, adapter, utils |
| **telegram** | Telegram интеграция | `TelegramUser`, `PersonalPlanSurvey`, `PersonalPlan` | views, serializers, authentication, services |
| **common** | Общие утилиты | - | audit, storage, validators, views (health checks) |

---

## 2. Главные модули

### 2.1 Цели КБЖУ (nutrition)
- **Модель**: `DailyGoal` с формулой Mifflin-St Jeor
- **Логика**: Автоматический расчет из `Profile` (вес, рост, возраст, активность, цель)
- **API**: `GET/PUT/PATCH /api/v1/nutrition/goals/`

### 2.2 Дневник питания (nutrition)
- **Модели**: `Meal` (приём пищи) -> `FoodItem` (блюда)
- **Логика**: Nested resources, агрегация КБЖУ по дням
- **API**: `/api/v1/meals/`, `/api/v1/meals/{id}/items/`

### 2.3 Фото-анализ (ai + ai_proxy)
- **Поток**: `AIRecognitionView` -> `AIProxyRecognitionService` -> `AIProxyClient` -> внешний сервис
- **Логика**: Base64/multipart -> распознавание -> создание `Meal` + `FoodItem`
- **Лимиты**: По тарифу (`daily_photo_limit`), throttling по IP

### 2.4 Подписки (billing)
- **Модели**: `SubscriptionPlan`, `Subscription`, `Payment`
- **Интеграция**: YooKassa (платежи, рекурренты, webhooks)
- **Логика**: FREE по умолчанию, PRO_MONTHLY/YEARLY с автопродлением

---

## 3. Слабые места и потенциальные баги

### 3.1 Критические проблемы

| # | Проблема | Файл | Риск |
|---|----------|------|------|
| 1 | **Дублирование данных КБЖУ**: `Profile.recommended_*` + `TelegramUser.recommended_*` + `DailyGoal` | models.py | Рассинхронизация |
| 2 | **Legacy поля в SubscriptionPlan**: `name` vs `code`, `max_photos_per_day` vs `daily_photo_limit` | billing/models.py | Путаница |
| 3 | **Отсутствие транзакций** в `save_test_results` при создании User/Profile/TelegramUser/DailyGoal | telegram/views.py | Data inconsistency |
| 4 | **Race condition** в `DailyGoal.save()` при деактивации других целей | nutrition/models.py | Duplicate active goals |

### 3.2 Архитектурные проблемы

| # | Проблема | Место | Рекомендация |
|---|----------|-------|--------------|
| 5 | **Бизнес-логика в views** (расчёт КБЖУ, создание Meal+FoodItem в AIRecognitionView) | ai/views.py, telegram/views.py | Вынести в services |
| 6 | **Дублирование кода аутентификации**: `TelegramWebAppAuthentication` + `webapp_auth_service` | telegram/ | Единый сервис |
| 7 | **Hardcoded значения**: `bot_username = "Fit_Coach_bot"` | telegram/views.py:782 | В settings |
| 8 | **Нет базового Exception класса** для доменных ошибок | везде | Создать иерархию |

### 3.3 Потенциальные баги

| # | Проблема | Файл | Симптом |
|---|----------|------|---------|
| 9 | `subscription.plan.name == 'FREE'` vs `plan.code` — несогласованность | billing/views.py | Неверная логика |
| 10 | В `days_remaining` не проверяется `is_active` перед вычислением | billing/models.py | Некорректные данные |
| 11 | `DailyUsage.objects.get_today()` может создать дубли при race condition | billing/usage.py | Duplicate records |
| 12 | Отсутствует очистка старых `EmailVerificationToken` (cleanup не запланирован) | users/services.py | DB bloat |

### 3.4 Точки отказа

| # | Компонент | Проблема | Митигация |
|---|-----------|----------|-----------|
| 13 | **AI Proxy** | Timeout 60s может быть недостаточен | Async processing, queue |
| 14 | **YooKassa webhooks** | Нет retry логики при сбое обработки | Idempotency, dead letter |
| 15 | **Signal post_save** для создания Profile/Subscription | Может упасть без транзакции | Explicit creation |

---

## 4. Roadmap рефакторинга

### Phase 1: Безопасные изменения (без ломки API)
**Срок: 1-2 недели**

| # | Задача | Приоритет | Файлы |
|---|--------|-----------|-------|
| 1.1 | Создать `apps/core/exceptions.py` с базовыми исключениями | High | новый файл |
| 1.2 | Добавить `@transaction.atomic` в критичные операции | High | telegram/views.py, billing/ |
| 1.3 | Исправить race condition в `DailyGoal.save()` | High | nutrition/models.py |
| 1.4 | Унифицировать использование `plan.code` вместо `plan.name` | High | billing/*.py |
| 1.5 | Вынести hardcoded значения в settings | Medium | telegram/views.py |
| 1.6 | Добавить celery task для `cleanup_expired_tokens()` | Medium | users/services.py |
| 1.7 | Добавить индексы в модели где отсутствуют | Medium | models.py |
| 1.8 | Покрыть unit-тестами критичные сервисы | Medium | tests/ |

### Phase 2: Структурный рефакторинг
**Срок: 2-3 недели**

| # | Задача | Приоритет | Файлы |
|---|--------|-----------|-------|
| 2.1 | Создать `nutrition/services.py` — вынести логику из views | High | новый файл |
| 2.2 | Создать `ai/services.py` — вынести создание Meal/FoodItem из AIRecognitionView | High | ai/views.py -> ai/services.py |
| 2.3 | Объединить Telegram аутентификацию в единый сервис | High | telegram/authentication.py, services/ |
| 2.4 | Удалить дублирование КБЖУ: оставить только в `DailyGoal` | Medium | Profile, TelegramUser |
| 2.5 | Убрать deprecated поля из `SubscriptionPlan` (миграция) | Medium | billing/models.py |
| 2.6 | Создать `billing/webhooks/` — выделить обработчики YooKassa | Medium | новая структура |
| 2.7 | Рефакторинг `telegram/views.py` — слишком большой файл (800+ строк) | Medium | split into modules |

### Phase 3: Оптимизация и стабилизация
**Срок: 2-3 недели**

| # | Задача | Приоритет | Файлы |
|---|--------|-----------|-------|
| 3.1 | Async обработка AI распознавания (Celery + Redis) | High | ai/, ai_proxy/ |
| 3.2 | Добавить retry логику для YooKassa webhooks | High | billing/ |
| 3.3 | Кэширование `get_effective_plan_for_user()` | Medium | billing/services.py |
| 3.4 | Добавить structured logging (JSON) | Medium | settings, audit.py |
| 3.5 | Интеграционные тесты для платежного потока | Medium | tests/ |
| 3.6 | API versioning strategy (v2 подготовка) | Low | urls.py |
| 3.7 | Документация API (OpenAPI annotations review) | Low | views.py |
| 3.8 | Performance profiling и оптимизация N+1 queries | Medium | views.py |

---

## 5. Метрики успеха

| Метрика | Текущее | Цель Phase 1 | Цель Phase 3 |
|---------|---------|--------------|--------------|
| Test coverage | ~10% | 40% | 70% |
| Cyclomatic complexity (max) | 15+ | 10 | 7 |
| N+1 queries | есть | минимизированы | устранены |
| Response time p95 | ~2s | ~1.5s | ~500ms |

---

## 6. Приоритеты для немедленного исправления

**TOP 5 критичных задач:**

1. **Race condition в DailyGoal** — может привести к нескольким активным целям у пользователя
2. **Транзакции в save_test_results** — при сбое создаются неполные записи
3. **Унификация plan.code vs plan.name** — разная логика в разных местах
4. **Дублирование КБЖУ данных** — источник правды неясен
5. **YooKassa webhook retry** — потеря платежей при сбое обработки

---

## Changelog

- **2025-12-06**: Первоначальный анализ и создание roadmap
