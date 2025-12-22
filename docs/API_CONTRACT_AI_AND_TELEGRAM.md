# API Contract: AI & Telegram Backend

> **SSOT (Single Source of Truth)** для всех интеграций с Backend.  
> Последнее обновление: 2025-12-22

---

## 1. Headers (SSOT)

### Обязательные заголовки для Auth endpoints

| Header | Описание | Обязателен |
|--------|----------|------------|
| `X-Telegram-Init-Data` | Строка initData от Telegram WebApp | ✅ Да (для auth) |
| `Content-Type` | `application/json` | ✅ Да |

### CORS Allowed Headers (Nginx)

```
Access-Control-Allow-Headers: 
  Content-Type,
  Authorization,
  X-Telegram-Init-Data,
  X-Request-ID,
  X-Bot-Secret
```

### Правила безопасности

> [!CAUTION]
> **В PROD debug bypass полностью ЗАПРЕЩЁН!**  
> - `DEBUG=False` в production
> - `DebugModeAuthentication` работает **ТОЛЬКО** при `settings.DEBUG=True`
> - Если `TELEGRAM_ADMINS` пуст в PROD → 403

---

## 2. Auth Endpoints

### `POST /api/v1/telegram/users/get-or-create/`

> Получить или создать пользователя по telegram_id (для бота).

**Request:**
```
Headers:
  X-Telegram-Init-Data: <initData string>  # Для WebApp
  X-Bot-Secret: <secret>                    # Для бота (альтернатива)
  
Query params (для бота):
  ?telegram_id=123456789&username=john&full_name=John%20Doe
```

**Response (200 OK):**
```json
{
  "id": 42,
  "user_id": 15,
  "telegram_id": 123456789,
  "username": "john_doe",
  "first_name": "John",
  "last_name": "Doe",
  "created": false
}
```

---

### `POST /api/v1/telegram/webapp/auth/`

> Универсальная авторизация Telegram WebApp → JWT + Profile.

**Request:**
```
Headers:
  X-Telegram-Init-Data: <initData string>
  Content-Type: application/json
```

**Response (200 OK):**
```json
{
  "user": {
    "id": 15,
    "telegram_id": 123456789,
    "username": "john_doe",
    "first_name": "John",
    "last_name": "Doe"
  },
  "profile": {
    "telegram_id": 123456789,
    "weight": 75,
    "height": 180,
    "goal_type": "weight_loss",
    "activity_level": "moderately_active"
  },
  "goals": {
    "calories": 2000,
    "protein": 150,
    "fat": 70,
    "carbohydrates": 200
  },
  "is_admin": false
}
```

---

## 3. AI Endpoints

### `POST /api/v1/ai/recognize/`

> Распознавание еды по фото (асинхронно).

**Request:**
```
Headers:
  Authorization: Bearer <jwt_token>
  Content-Type: multipart/form-data

Body (form-data):
  image: <file>          # JPEG/PNG
  meal_type: "breakfast" # breakfast|lunch|dinner|snack
  date: "2025-12-22"     # YYYY-MM-DD
  user_comment: "..."    # опционально
```

**Response (202 Accepted) — ASYNC режим (основной):**
```json
{
  "task_id": "abc123-def456-ghi789",
  "meal_id": 42,
  "status": "processing"
}
```

**Response Headers:**
```
X-Request-ID: 7f8a9b0c1d2e3f4a
```

---

### `GET /api/v1/ai/task/<task_id>/`

> Polling статуса задачи распознавания.

**Request:**
```
Headers:
  Authorization: Bearer <jwt_token>
```

**Response (200 OK) — Processing:**
```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "processing",
  "state": "STARTED"
}
```

**Response (200 OK) — Success:**
```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "success",
  "state": "SUCCESS",
  "result": {
    "meal_id": 42,
    "items": [
      {
        "name": "Куриная грудка",
        "amount_grams": 150,
        "calories": 165,
        "protein": 31,
        "fat": 3.6,
        "carbohydrates": 0
      }
    ],
    "totals": {
      "calories": 165,
      "protein": 31,
      "fat": 3.6,
      "carbohydrates": 0
    }
  }
}
```

**Response (200 OK) — Failed:**
```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "failed",
  "state": "FAILURE",
  "error": "AI processing failed"
}
```

### Статусы, ошибки, таймауты

| State | Status | Описание |
|-------|--------|----------|
| `PENDING` | `processing` | Задача в очереди |
| `STARTED` | `processing` | Задача выполняется |
| `RETRY` | `processing` | Retry после ошибки |
| `SUCCESS` | `success` | Успешно завершена |
| `FAILURE` | `failed` | Ошибка (details в логах) |

**Рекомендованный polling:**
- Интервал: 1-2 секунды
- Таймаут клиента: 60 секунд
- Таймаут сервера (Celery): 90 секунд

---

## 4. Billing Endpoints

### `GET /api/v1/billing/plans/` (PUBLIC)

> Список активных тарифных планов.

**Request:** без авторизации

**Response (200 OK):**
```json
[
  {
    "code": "FREE",
    "display_name": "Free",
    "price": "0.00",
    "duration_days": null,
    "daily_photo_limit": 3,
    "history_days": 7,
    "ai_recognition": true,
    "advanced_stats": false,
    "priority_support": false
  },
  {
    "code": "PRO_MONTHLY",
    "display_name": "PRO (Месяц)",
    "price": "299.00",
    "duration_days": 30,
    "daily_photo_limit": null,
    "history_days": null,
    "ai_recognition": true,
    "advanced_stats": true,
    "priority_support": true
  }
]
```

> [!IMPORTANT]
> **Тип `price`:** строка (Decimal в JSON). Парсить как `parseFloat(price)`.  
> **Коды тарифов:** `FREE`, `PRO_MONTHLY`, `PRO_YEARLY`, `TEST_LIVE` (только для админов).

---

### `GET /api/v1/billing/me/` (AUTH)

> Короткий статус подписки для UI.

**Request:**
```
Headers:
  Authorization: Bearer <jwt_token>
```

**Response (200 OK):**
```json
{
  "plan_code": "FREE",
  "plan_name": "Free",
  "expires_at": null,
  "is_active": true,
  "daily_photo_limit": 3,
  "used_today": 1,
  "remaining_today": 2,
  "test_live_payment_available": false
}
```

**Для PRO подписки:**
```json
{
  "plan_code": "PRO_MONTHLY",
  "plan_name": "PRO (Месяц)",
  "expires_at": "2025-01-22T00:00:00+00:00",
  "is_active": true,
  "daily_photo_limit": null,
  "used_today": 15,
  "remaining_today": null,
  "test_live_payment_available": false
}
```

> [!NOTE]
> - `daily_photo_limit: null` означает безлимит
> - `remaining_today: null` означает безлимит
> - `expires_at: null` для FREE плана

---

## 5. Ошибки (Единый формат)

### Формат ошибки

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Человекочитаемое описание"
  }
}
```

или (для простых случаев):

```json
{
  "error": "Краткое описание"
}
```

---

### 401 Unauthorized — нет/невалидный initData

**Причина:** Отсутствует или невалидный `X-Telegram-Init-Data`

```json
{
  "error": "Authentication failed"
}
```

**Причина:** Невалидная подпись initData

```json
{
  "detail": "Нет доступа"
}
```

> [!TIP]
> Проверь:
> 1. Заголовок `X-Telegram-Init-Data` присутствует
> 2. `TELEGRAM_BOT_TOKEN` совпадает на backend и при генерации initData
> 3. initData не expired (проверь `auth_date`)

---

### 429 Too Many Requests — лимит

**AI Recognition (дневной лимит):**
```json
{
  "detail": "Request was throttled. Expected available in 86400 seconds."
}
```

**Payments (rate limit):**
```json
{
  "detail": "Request was throttled. Expected available in 3600 seconds."
}
```

**Personal Plan (дневной лимит):**
```json
{
  "error": "Daily limit of 3 plans reached"
}
```

---

### 500 Internal Server Error

```json
{
  "error": "Internal server error"
}
```

или для Billing:

```json
{
  "error": {
    "code": "PAYMENT_CREATE_FAILED",
    "message": "Не удалось создать платеж. Попробуйте позже."
  }
}
```

**YooKassa специфичные:**

```json
{
  "error": {
    "code": "YOOKASSA_API_ERROR",
    "message": "Ошибка платёжной системы. Попробуйте позже."
  }
}
```

---

## Quick Reference

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/telegram/users/get-or-create/` | GET | Bot Secret | Get/create user |
| `/api/v1/telegram/webapp/auth/` | POST | initData | WebApp auth |
| `/api/v1/ai/recognize/` | POST | JWT | AI photo recognition |
| `/api/v1/ai/task/<id>/` | GET | JWT | Poll task status |
| `/api/v1/billing/plans/` | GET | — | List plans (public) |
| `/api/v1/billing/me/` | GET | JWT | Subscription status |

---

## Changelog

- **2025-12-22**: Initial version
