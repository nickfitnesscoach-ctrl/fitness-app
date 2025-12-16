# Архитектура Telegram Backend

| | |
|---|---|
| **Статус** | production-ready |
| **Владелец** | `apps/telegram/` |
| **Проверено** | 2024-12-16 |
| **Правило** | Меняешь код в `apps/telegram/*` → обнови docs |

---

## Структура каталогов

```
apps/telegram/
├── __init__.py
├── admin.py                  # Django Admin регистрация
├── apps.py                   # AppConfig + сигналы
├── models.py                 # TelegramUser, PersonalPlanSurvey, PersonalPlan
├── serializers.py            # DRF сериализаторы (вход/выход)
├── telegram_auth.py          # Admin permission + middleware
├── tests.py                  # Тесты
├── urls.py                   # Маршрутизация API
│
├── auth/                     # Аутентификация WebApp
│   ├── __init__.py
│   ├── authentication.py     # DRF authentication backends
│   ├── views.py              # /auth/, /webapp/auth/, /trainer/admin-panel/
│   └── services/
│       └── webapp_auth.py    # Проверка initData (HMAC)
│
├── bot/                      # Bot API
│   ├── __init__.py
│   └── views.py              # /save-test/, /users/get-or-create/, ...
│
├── trainer_panel/            # Панель тренера
│   ├── __init__.py
│   ├── views.py              # /applications/, /clients/, /subscribers/
│   ├── billing_adapter.py    # Адаптер к apps/billing/
│   ├── urls.py               # (не используется, URL в корневом urls.py)
│   └── test_subscriptions.py # Тесты подписок
│
├── migrations/               # Django миграции
└── docs/                     # Эта документация
```

---

## Почему домены разделены

### auth/ — Аутентификация

**Ответственность:** Превратить запрос от Telegram в авторизованного Django User.

```
┌─────────────────────────────────────────────────────────────────┐
│                          auth/                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────┐    ┌──────────────────────┐           │
│  │   authentication.py  │    │   services/          │           │
│  │                      │    │   webapp_auth.py     │           │
│  │ • TelegramWebApp     │───▶│                      │           │
│  │   Authentication     │    │ • validate_init_data │           │
│  │ • DebugMode          │    │ • get_user_data      │           │
│  │   Authentication     │    │ • HMAC verification  │           │
│  └──────────────────────┘    └──────────────────────┘           │
│              │                                                   │
│              ▼                                                   │
│  ┌──────────────────────┐                                       │
│  │      views.py        │                                       │
│  │                      │                                       │
│  │ • telegram_auth      │ → JWT токены                          │
│  │ • webapp_auth        │ → user + profile + goals              │
│  │ • trainer_panel_auth │ → проверка TELEGRAM_ADMINS            │
│  │ • telegram_profile   │ → профиль пользователя                │
│  └──────────────────────┘                                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Почему отдельно:**
- Критически важный код безопасности
- Используется всеми остальными частями
- Требует особого внимания при ревью

---

### bot/ — Bot API

**Ответственность:** Обслуживать запросы от Telegram-бота.

```
┌─────────────────────────────────────────────────────────────────┐
│                           bot/                                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │                     views.py                          │       │
│  │                                                       │       │
│  │  ┌─────────────────┐  ┌─────────────────┐            │       │
│  │  │ save_test_      │  │ get_user_or_    │            │       │
│  │  │ results         │  │ create          │            │       │
│  │  │                 │  │                 │            │       │
│  │  │ Сохраняет       │  │ Создаёт/ищет    │            │       │
│  │  │ AI-тест +       │  │ TelegramUser    │            │       │
│  │  │ профиль +       │  │                 │            │       │
│  │  │ DailyGoal       │  │                 │            │       │
│  │  └─────────────────┘  └─────────────────┘            │       │
│  │                                                       │       │
│  │  ┌─────────────────┐  ┌─────────────────┐            │       │
│  │  │ create_survey   │  │ create_plan     │            │       │
│  │  │                 │  │                 │            │       │
│  │  │ Создаёт анкету  │  │ Сохраняет       │            │       │
│  │  │ PersonalPlan    │  │ AI-план         │            │       │
│  │  │ Survey          │  │                 │            │       │
│  │  └─────────────────┘  └─────────────────┘            │       │
│  │                                                       │       │
│  │  ┌─────────────────┐  ┌─────────────────┐            │       │
│  │  │ count_plans_    │  │ get_invite_     │            │       │
│  │  │ today           │  │ link            │            │       │
│  │  │                 │  │                 │            │       │
│  │  │ Лимит планов/   │  │ Публичная       │            │       │
│  │  │ день            │  │ ссылка на бота  │            │       │
│  │  └─────────────────┘  └─────────────────┘            │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  Все endpoint'ы (кроме invite-link) требуют X-Bot-Secret        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Почему отдельно:**
- Другой механизм авторизации (X-Bot-Secret вместо initData)
- Write-операции от имени бота
- Отдельная зона ответственности

---

### trainer_panel/ — Панель тренера

**Ответственность:** API для административной панели.

```
┌─────────────────────────────────────────────────────────────────┐
│                       trainer_panel/                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │                     views.py                          │       │
│  │                                                       │       │
│  │  ┌─────────────────┐  ┌─────────────────┐            │       │
│  │  │ get_applications│  │ clients_list    │            │       │
│  │  │ _api            │  │                 │            │       │
│  │  │                 │  │ GET: клиенты    │            │       │
│  │  │ Все прошедшие   │  │ POST: добавить  │            │       │
│  │  │ AI-тест         │  │ в клиенты       │            │       │
│  │  └─────────────────┘  └─────────────────┘            │       │
│  │                                                       │       │
│  │  ┌─────────────────┐  ┌─────────────────┐            │       │
│  │  │ client_detail   │  │ get_subscribers │            │       │
│  │  │                 │  │ _api            │            │       │
│  │  │ DELETE: убрать  │  │                 │            │       │
│  │  │ из клиентов     │  │ Статистика      │            │       │
│  │  │                 │  │ подписок/       │            │       │
│  │  │                 │  │ выручки         │            │       │
│  │  └─────────────────┘  └─────────────────┘            │       │
│  └──────────────────────────────────────────────────────┘       │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────┐       │
│  │                 billing_adapter.py                    │       │
│  │                                                       │       │
│  │  • get_user_subscription_info()                       │       │
│  │  • get_subscriptions_for_users() ← batch, без N+1     │       │
│  │  • get_subscribers_metrics()                          │       │
│  │  • get_revenue_metrics()                              │       │
│  └──────────────────────────────────────────────────────┘       │
│                              │                                   │
│                              ▼                                   │
│                       apps/billing/                              │
│                                                                  │
│  Все endpoint'ы требуют TelegramAdminPermission                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Почему отдельно:**
- Только для администраторов
- Своя логика отображения данных
- Изоляция от основного функционала

---

## SSOT (Single Source of Truth)

### Где живут какие данные

| Данные | SSOT | Копии/кеши |
|--------|------|------------|
| Пользователь | `auth.User` | (нигде) |
| Telegram ID/username | `TelegramUser` | `Profile.telegram_id` (legacy) |
| Профиль (вес, рост, цели) | `Profile` | `TelegramUser.ai_test_answers` |
| Дневные цели КБЖУ | `DailyGoal` | `TelegramUser.recommended_*` |
| Подписка | `Subscription` | Приходит через `billing_adapter` |
| AI-тест ответы | `TelegramUser.ai_test_answers` | (дополнительно в `Profile`) |
| Анкета PersonalPlan | `PersonalPlanSurvey` | (нигде) |
| AI-план | `PersonalPlan` | (нигде) |

### Принцип

> [!IMPORTANT]
> Django User — центральная сущность. Все остальные модели ссылаются на неё через ForeignKey или OneToOne.

```
              ┌─────────────┐
              │ Django User │
              └─────────────┘
                     │
     ┌───────────────┼───────────────┐
     │               │               │
     ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│TelegramUser │ │  Profile    │ │Subscription │
│  (1:1)      │ │  (1:1)      │ │  (1:1)      │
└─────────────┘ └─────────────┘ └─────────────┘
     │
     ▼
┌─────────────┐    ┌─────────────┐
│PersonalPlan │───▶│PersonalPlan │
│Survey (1:N) │    │  (1:N)      │
└─────────────┘    └─────────────┘
```

---

## Почему billing вынесен через adapter

### Проблема

Trainer Panel нужны данные о подписках (`is_paid`, `plan_type`, `paid_until`), но:
- `apps/billing/` — отдельный домен со своей логикой
- Модели billing могут меняться независимо
- Нужно избежать N+1 запросов при показе списка клиентов

### Решение

`trainer_panel/billing_adapter.py` — тонкий слой, который:

1. **Инкапсулирует обращения к billing**
   ```python
   from apps.billing.models import Payment, Subscription
   # Только billing_adapter импортирует модели billing
   ```

2. **Предоставляет batch-методы**
   ```python
   get_subscriptions_for_users(user_ids: List[int]) -> Dict[int, SubscriptionInfo]
   # Один запрос вместо N
   ```

3. **Нормализует данные для фронта**
   ```python
   _normalize_plan_code("PRO_MONTHLY") -> "monthly"
   # Фронт получает единообразные значения
   ```

4. **Изолирует изменения**
   - Если billing меняет структуру — правим только adapter
   - Views панели тренера не затрагиваются

### Пример использования

```python
# trainer_panel/views.py

from apps.telegram.trainer_panel.billing_adapter import get_subscriptions_for_users

def get_applications_api(request):
    clients = list(qs[offset : offset + limit])
    
    # Один batch-запрос вместо N
    user_ids = [c.user_id for c in clients]
    subscriptions_map = get_subscriptions_for_users(user_ids)
    
    for client in clients:
        subscription = subscriptions_map.get(client.user_id, default_subscription())
        # ...
```

---

## Маршрутизация (urls.py)

Все URL Telegram-домена зарегистрированы в `apps/telegram/urls.py`:

```python
urlpatterns = [
    # Auth
    path('auth/', telegram_auth),
    path('webapp/auth/', webapp_auth),
    path('trainer/admin-panel/', trainer_panel_auth),
    path('profile/', telegram_profile),
    
    # Bot API
    path('save-test/', save_test_results),
    path('users/get-or-create/', get_user_or_create),
    path('personal-plan/survey/', create_survey),
    path('personal-plan/plan/', create_plan),
    path('personal-plan/count-today/', count_plans_today),
    path('invite-link/', get_invite_link),
    
    # Trainer Panel
    path('applications/', get_applications_api),
    path('clients/', clients_list),
    path('clients/<int:client_id>/', client_detail),
    path('subscribers/', get_subscribers_api),
]
```

Подключение к основному роутеру (в `config/urls.py`):
```python
path('api/v1/telegram/', include('apps.telegram.urls')),
```

---

## Связи с другими модулями

```
                        apps/telegram/
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
    apps/users/          apps/billing/      apps/nutrition/
          │                   │                   │
    • Profile            • Subscription       • DailyGoal
    • Django User        • Payment            • Meal
                         • Plan
```

### Импорты

| Telegram модуль | Импортирует из |
|-----------------|----------------|
| `auth/authentication.py` | `apps.telegram.models`, `apps.users.models` |
| `auth/views.py` | `apps.nutrition.models`, `apps.telegram.models`, `apps.users.models` |
| `bot/views.py` | `apps.nutrition.models`, `apps.telegram.models` |
| `trainer_panel/views.py` | `apps.telegram.models` |
| `trainer_panel/billing_adapter.py` | `apps.billing.models` |

> [!NOTE]
> `billing_adapter.py` — единственное место, где trainer_panel обращается к billing.
