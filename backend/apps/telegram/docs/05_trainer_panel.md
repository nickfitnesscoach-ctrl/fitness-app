# Trainer Panel (Backend)

| | |
|---|---|
| **Статус** | production-ready |
| **Владелец** | `apps/telegram/trainer_panel/` |
| **Проверено** | 2024-12-16 |
| **Правило** | Меняешь код в `apps/telegram/*` → обнови docs |

---

## Назначение

Trainer Panel — это административный интерфейс для тренера/владельца бизнеса. Backend предоставляет API для:

- Просмотра заявок (все кто прошёл AI-тест)
- Управления клиентами (добавление/удаление)
- Статистики подписок и выручки

> [!IMPORTANT]
> Trainer Panel — это Telegram WebApp, а не отдельный сайт. Доступ возможен только через Telegram.

---

## Аутентификация и авторизация

### Как тренер заходит в панель

```
┌─────────────────────────────────────────────────────────────────┐
│                     Telegram Mini App                            │
│                                                                  │
│  1. Тренер открывает Mini App с кнопки в боте                   │
│  2. Telegram передаёт initData                                  │
│  3. Frontend отправляет POST /api/v1/telegram/trainer/admin-panel/
│  4. Backend проверяет:                                           │
│     - initData валиден?                                          │
│     - telegram_id ∈ TELEGRAM_ADMINS?                            │
│  5. Если да → { ok: true, role: "admin" }                       │
│  6. Если нет → 403 Forbidden                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Почему Trainer Panel — это Telegram WebApp

| Альтернатива | Проблемы |
|--------------|----------|
| Отдельный сайт с логином | Нужен отдельный механизм аутентификации |
| OAuth через Telegram | Сложнее, требует публичный backend |
| JWT из бота | Небезопасно без дополнительной верификации |

**WebApp решает:**
- Аутентификация "из коробки" через initData
- Единый UX с основным Mini App
- Проверка администратора на backend

### Защита эндпоинтов

Все эндпоинты Trainer Panel используют `TelegramAdminPermission`:

```python
@api_view(["GET"])
@permission_classes([TelegramAdminPermission])
def get_applications_api(request):
    ...
```

`TelegramAdminPermission` проверяет:
1. Есть ли `X-Telegram-Init-Data` в заголовках
2. Валидна ли подпись initData
3. Есть ли `telegram_id` в `settings.TELEGRAM_ADMINS`

---

## API Эндпоинты

### POST `/api/v1/telegram/trainer/admin-panel/`

**Назначение:** Авторизация в Trainer Panel.

**Защита:** initData + проверка TELEGRAM_ADMINS

**Тело запроса:**

```json
{
  "init_data": "user=%7B%22id%22%3A123...&hash=abc..."
}
```

Или заголовок:
```
X-Telegram-Init-Data: user=%7B%22id%22%3A123...&hash=abc...
```

**Успешный ответ:**

```json
{
  "ok": true,
  "role": "admin"
}
```

**Ошибка (не админ):**

```json
{
  "detail": "Нет доступа"
}
```

---

### GET `/api/v1/telegram/applications/`

**Назначение:** Список всех заявок (кто прошёл AI-тест).

**Защита:** TelegramAdminPermission

**Query параметры:**

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `limit` | 200 | Количество записей (max 1000) |
| `offset` | 0 | Смещение для пагинации |

**Ответ:**

```json
[
  {
    "id": 15,
    "telegram_id": "123456789",
    "first_name": "Иван",
    "last_name": "Петров",
    "username": "ivan_petrov",
    "photo_url": "",
    "status": "new",
    "display_name": "Иван Петров",
    "ai_test_completed": true,
    "details": {
      "gender": "male",
      "age": 30,
      "weight": 80,
      "goal": "weight_loss"
    },
    "recommended_calories": 2000,
    "recommended_protein": "150.00",
    "recommended_fat": "66.67",
    "recommended_carbs": "200.00",
    "created_at": "2024-12-16T10:30:00+03:00",
    "subscription": {
      "plan_type": "monthly",
      "is_paid": true,
      "status": "active",
      "paid_until": "2025-01-16T10:30:00+03:00"
    },
    "is_paid": true
  }
]
```

**Поля статуса:**

| status | Значение |
|--------|----------|
| `"new"` | Заявка не обработана (`is_client = False`) |
| `"contacted"` | Добавлен в клиенты (`is_client = True`) |

---

### GET `/api/v1/telegram/clients/`

**Назначение:** Список клиентов (is_client = True).

**Защита:** TelegramAdminPermission

**Query параметры:** Аналогично `/applications/`

**Ответ:** Аналогичен `/applications/`, но только записи с `is_client = True`.

---

### POST `/api/v1/telegram/clients/`

**Назначение:** Добавить заявку в клиенты.

**Защита:** TelegramAdminPermission

**Тело запроса:**

```json
{
  "id": 15
}
```

> [!NOTE]
> `id` — это ID записи `TelegramUser`, не `telegram_id`.

**Успешный ответ:**

```json
{
  "status": "success",
  "message": "Client added successfully",
  "id": 15
}
```

**Если уже клиент:**

```json
{
  "status": "success",
  "message": "Client already added",
  "id": 15
}
```

**Ошибки:**

| Код | Причина |
|-----|---------|
| 400 | `id` не указан или не число |
| 400 | Пользователь не прошёл AI-тест |
| 404 | TelegramUser не найден |

---

### DELETE `/api/v1/telegram/clients/{client_id}/`

**Назначение:** Убрать из клиентов (вернуть в заявки).

**Защита:** TelegramAdminPermission

**Path параметры:**

| Параметр | Описание |
|----------|----------|
| `client_id` | ID записи TelegramUser |

**Успешный ответ:**

```json
{
  "status": "success",
  "message": "Client removed successfully"
}
```

**Если уже не клиент:**

```json
{
  "status": "success",
  "message": "Client already removed"
}
```

---

### GET `/api/v1/telegram/subscribers/`

**Назначение:** Статистика подписчиков и выручки.

**Защита:** TelegramAdminPermission

**Query параметры:**

| Параметр | По умолчанию | Описание |
|----------|--------------|----------|
| `limit` | 200 | Количество подписчиков в списке |
| `offset` | 0 | Смещение для пагинации |

**Ответ:**

```json
{
  "subscribers": [
    {
      "id": 15,
      "telegram_id": 123456789,
      "first_name": "Иван",
      "last_name": "Петров",
      "username": "ivan_petrov",
      "plan_type": "monthly",
      "subscribed_at": "2024-12-01T10:30:00+03:00",
      "expires_at": "2025-01-01T10:30:00+03:00",
      "is_active": true
    }
  ],
  "stats": {
    "total": 150,
    "free": 100,
    "monthly": 40,
    "yearly": 10,
    "revenue": 45000.00
  }
}
```

**Метрики в `stats`:**

| Поле | Описание |
|------|----------|
| `total` | Всего пользователей |
| `free` | Бесплатные пользователи |
| `monthly` | Активные месячные подписки |
| `yearly` | Активные годовые подписки |
| `revenue` | Общая выручка (RUB) |

---

## Billing Adapter

Trainer Panel не обращается напрямую к `apps/billing/`. Вместо этого используется адаптер:

```python
# trainer_panel/billing_adapter.py

def get_subscriptions_for_users(user_ids: List[int]) -> Dict[int, SubscriptionInfo]:
    """Batch-получение подписок (без N+1)."""
    
def get_subscribers_metrics() -> SubscribersCounts:
    """Метрики: free/monthly/yearly/paid_total."""
    
def get_revenue_metrics() -> RevenueMetrics:
    """Выручка: total/mtd/last_30d."""
```

### Формат SubscriptionInfo

```python
{
    "plan_type": "monthly",    # free | monthly | yearly
    "is_paid": True,           # True если платная + активная
    "status": "active",        # active | expired | canceled | unknown
    "paid_until": "2025-01-16T10:30:00+03:00"  # ISO string или None
}
```

### Нормализация plan_code

Backend billing может хранить разные коды (`PRO_MONTHLY`, `MONTHLY`, etc.), адаптер нормализует:

| Из billing | Для frontend |
|------------|--------------|
| `FREE` | `free` |
| `PRO_MONTHLY`, `MONTHLY` | `monthly` |
| `PRO_YEARLY`, `YEARLY` | `yearly` |

---

## Пагинация

Все списочные эндпоинты поддерживают пагинацию:

```
GET /api/v1/telegram/applications/?limit=50&offset=100
```

**Ограничения:**
- `limit` по умолчанию: 200
- `limit` максимум: 1000
- `offset` минимум: 0

---

## Frontend интеграция

### Заголовки

Frontend должен передавать initData в каждом запросе:

```javascript
const response = await fetch('/api/v1/telegram/applications/', {
  headers: {
    'X-Telegram-Init-Data': window.Telegram.WebApp.initData,
    'Content-Type': 'application/json',
  },
});
```

### Обработка 403

Если пользователь не админ:

```javascript
if (response.status === 403) {
  // Показать сообщение "Нет доступа"
  // Перенаправить на главный экран Mini App
}
```

### Добавление в клиенты

```javascript
async function addToClients(telegramUserId) {
  const response = await fetch('/api/v1/telegram/clients/', {
    method: 'POST',
    headers: {
      'X-Telegram-Init-Data': window.Telegram.WebApp.initData,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ id: telegramUserId }),
  });
  
  const data = await response.json();
  if (data.status === 'success') {
    // Обновить UI
  }
}
```

---

## Сводная таблица

| Endpoint | Метод | Защита | Описание |
|----------|-------|--------|----------|
| `/trainer/admin-panel/` | POST | initData + ADMINS | Авторизация в панели |
| `/applications/` | GET | TelegramAdminPermission | Все заявки |
| `/clients/` | GET | TelegramAdminPermission | Только клиенты |
| `/clients/` | POST | TelegramAdminPermission | Добавить в клиенты |
| `/clients/{id}/` | DELETE | TelegramAdminPermission | Убрать из клиентов |
| `/subscribers/` | GET | TelegramAdminPermission | Статистика |

---

## Частые ошибки (Debugging)

> [!TIP]
> Чек-лист для диагностики: проверяй по порядку, пока не найдёшь причину.

### 403 на `/trainer/admin-panel/`

```
1. ✅ initData передаётся?
   → Проверь заголовок X-Telegram-Init-Data
   
2. ✅ initData валиден?
   → Проверь время сервера (auth_date + TTL)
   → Проверь TELEGRAM_BOT_TOKEN в .env
   
3. ✅ telegram_id в TELEGRAM_ADMINS?
   → Проверь settings.py / .env
   → Формат: [123456789] или "123456789"
```

### initData валиден, но 403 (не админ)

```
1. ✅ Это ожидаемое поведение
   → initData от обычного пользователя
   
2. ✅ Проверь telegram_id пользователя
   → Добавь в TELEGRAM_ADMINS если нужен доступ
```

### В DEV работает, в PROD — нет

```
1. ✅ DEBUG=False в production?
   → Debug Mode auth не работает в PROD
   
2. ✅ WEBAPP_DEBUG_MODE_ENABLED?
   → Должен быть False в PROD
   
3. ✅ TELEGRAM_ADMINS заполнен?
   → В DEV пустой = доступ для всех
   → В PROD пустой = 403 для всех
```

### 500 на endpoint'ах Trainer Panel

```
1. ✅ Миграции применены?
   → python manage.py migrate telegram
   → python manage.py migrate billing
   
2. ✅ billing_adapter работает?
   → Проверь связь User → Subscription
   → Нет Subscription = fallback на "free"
   
3. ✅ Логи сервера?
   → Traceback покажет конкретную ошибку
```

### Frontend: данные не загружаются

```
1. ✅ initData передаётся в каждом запросе?
   → headers: { 'X-Telegram-Init-Data': ... }
   
2. ✅ Content-Type правильный?
   → 'application/json' для POST
   
3. ✅ Network tab показывает 200?
   → Если 403 — см. выше
   → Если 500 — проверь backend логи
```

### Клиент не добавляется (400)

```
1. ✅ Передаёшь правильный id?
   → Нужен TelegramUser.id, не telegram_id
   
2. ✅ Пользователь прошёл AI-тест?
   → ai_test_completed должен быть True
   → Иначе 400: "Пользователь не прошёл тест"
```

