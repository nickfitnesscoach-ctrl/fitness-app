# Billing & Settings API Documentation

**Base URL:** `/api/v1/billing/`
**Authentication:** Telegram WebApp или JWT Token (обязательно)

---

## Overview

Эти эндпоинты обеспечивают полную информацию для экрана "Настройки" и управления подпиской. Все эндпоинты требуют аутентификации через Telegram WebApp или JWT.

---

## Endpoints

### 1. GET `/subscription/`

**Описание:** Получение полной информации о подписке пользователя для экрана "Настройки".

**Авторизация:** Требуется (Telegram WebApp / JWT)

#### Response 200 OK:

```json
{
  "plan": "free",                          // "free" | "pro"
  "plan_display": "Free",                  // "Free" | "PRO"
  "expires_at": "2025-12-26",             // YYYY-MM-DD или null (для free)
  "is_active": true,                       // Активна ли подписка сейчас
  "autorenew_available": false,            // Доступно ли автопродление (есть ли карта)
  "autorenew_enabled": false,              // Включено ли автопродление
  "payment_method": {
    "is_attached": false,                  // Привязана ли карта
    "card_mask": null,                     // "•••• 1234" или null
    "card_brand": null                     // "Visa", "MasterCard", "МИР" или null
  }
}
```

#### Примеры ответов:

**Пользователь без подписки (Free):**
```json
{
  "plan": "free",
  "plan_display": "Free",
  "expires_at": null,
  "is_active": true,
  "autorenew_available": false,
  "autorenew_enabled": false,
  "payment_method": {
    "is_attached": false,
    "card_mask": null,
    "card_brand": null
  }
}
```

**Пользователь с PRO без карты:**
```json
{
  "plan": "pro",
  "plan_display": "PRO",
  "expires_at": "2025-03-15",
  "is_active": true,
  "autorenew_available": false,  // Нет карты
  "autorenew_enabled": false,
  "payment_method": {
    "is_attached": false,
    "card_mask": null,
    "card_brand": null
  }
}
```

**Пользователь с PRO и привязанной картой:**
```json
{
  "plan": "pro",
  "plan_display": "PRO",
  "expires_at": "2025-03-15",
  "is_active": true,
  "autorenew_available": true,
  "autorenew_enabled": true,
  "payment_method": {
    "is_attached": true,
    "card_mask": "•••• 1234",
    "card_brand": "Visa"
  }
}
```

#### Error 401 Unauthorized:
```json
{
  "detail": "Authentication credentials were not provided."
}
```

---

### 2. POST `/subscription/autorenew/`

**Описание:** Включение или отключение автопродления подписки.

**Авторизация:** Требуется

#### Request Body:
```json
{
  "enabled": true    // true для включения, false для отключения
}
```

#### Response 200 OK:

Возвращает тот же формат, что и `GET /subscription/` с обновленными данными.

```json
{
  "plan": "pro",
  "plan_display": "PRO",
  "expires_at": "2025-03-15",
  "is_active": true,
  "autorenew_available": true,
  "autorenew_enabled": true,         // Обновленное значение
  "payment_method": {
    "is_attached": true,
    "card_mask": "•••• 1234",
    "card_brand": "Visa"
  }
}
```

#### Error 400 Bad Request (нет привязанной карты):
```json
{
  "error": {
    "code": "payment_method_required",
    "message": "Для автопродления необходима привязанная карта. Оформите подписку с сохранением карты."
  }
}
```

#### Error 400 Bad Request (бесплатный план):
```json
{
  "error": {
    "code": "NOT_AVAILABLE_FOR_FREE",
    "message": "Автопродление недоступно для бесплатного плана"
  }
}
```

#### Error 404 Not Found (нет подписки):
```json
{
  "error": {
    "code": "NO_SUBSCRIPTION",
    "message": "У вас нет активной подписки"
  }
}
```

---

### 3. GET `/payment-method/`

**Описание:** Получение информации о привязанном способе оплаты.

**Авторизация:** Требуется

#### Response 200 OK:
```json
{
  "is_attached": true,
  "card_mask": "•••• 1234",
  "card_brand": "Visa"
}
```

#### Примеры:

**Нет привязанной карты:**
```json
{
  "is_attached": false,
  "card_mask": null,
  "card_brand": null
}
```

**Есть привязанная карта:**
```json
{
  "is_attached": true,
  "card_mask": "•••• 5678",
  "card_brand": "MasterCard"
}
```

---

### 4. GET `/payments/`

**Описание:** Получение истории платежей пользователя.

**Авторизация:** Требуется

#### Query Parameters:
- `limit` (optional, integer, default: 10): Количество платежей (1-100)

#### Response 200 OK:
```json
{
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "amount": 299.00,
      "currency": "RUB",
      "status": "succeeded",             // "pending" | "succeeded" | "canceled" | "failed" | "refunded"
      "paid_at": "2025-02-10T12:34:56Z", // ISO 8601 или null
      "description": "Подписка Pro Месячный"
    },
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "amount": 299.00,
      "currency": "RUB",
      "status": "pending",
      "paid_at": null,
      "description": "Подписка Pro Месячный"
    }
  ]
}
```

#### Примечания:
- Платежи отсортированы от новых к старым
- Возвращаются только платежи текущего пользователя
- Максимум `limit` платежей

#### Example Request:
```bash
GET /api/v1/billing/payments/?limit=5
```

#### Example Response (пустой список):
```json
{
  "results": []
}
```

---

## Contract Guarantees

### 1. Структура ответа `/subscription/`

**Гарантии:**
- Все поля всегда присутствуют (никогда не `undefined`)
- `plan` всегда `"free"` или `"pro"` (lowercase)
- `plan_display` всегда `"Free"` или `"PRO"` (капитализация)
- `expires_at`: `null` для free, `"YYYY-MM-DD"` для pro
- `is_active`: boolean
- `autorenew_available`: boolean (зависит от наличия `payment_method`)
- `autorenew_enabled`: boolean
- `payment_method` всегда объект с тремя полями:
  - `is_attached`: boolean
  - `card_mask`: string | null
  - `card_brand`: string | null

### 2. Структура ответа `/payments/`

**Гарантии:**
- `results` всегда массив (может быть пустым)
- Каждый элемент массива содержит:
  - `id`: UUID string
  - `amount`: number (float)
  - `currency`: string (обычно "RUB")
  - `status`: один из `["pending", "succeeded", "canceled", "failed", "refunded"]` (lowercase)
  - `paid_at`: ISO 8601 string | null
  - `description`: string
- Порядок: от новых к старым (по `created_at`)

### 3. Формат ошибок

**Гарантии:**
- Все ошибки содержат объект `error`:
```json
{
  "error": {
    "code": "ERROR_CODE",        // UPPERCASE_SNAKE_CASE или camelCase
    "message": "Human readable"  // Русский язык
  }
}
```

**Коды ошибок:**
- `payment_method_required`: Нет привязанной карты для автопродления
- `NOT_AVAILABLE_FOR_FREE`: Операция недоступна для бесплатного плана
- `NO_SUBSCRIPTION`: У пользователя нет подписки

### 4. HTTP статусы

**Разрешённые коды:**
- `200` — успех
- `400` — ошибка валидации / бизнес-логики
- `401` — не авторизован
- `404` — подписка не найдена

---

## Integration Notes

### Обновление информации о карте

Информация о карте (`card_mask`, `card_brand`) автоматически сохраняется при успешной оплате через YooKassa webhook. После успешной оплаты:

1. Webhook `payment.succeeded` получает данные о карте
2. Сохраняет `yookassa_payment_method_id`, `card_mask`, `card_brand` в модель `Subscription`
3. Автоматически включает `auto_renew = True`

### Безопасность

- Все эндпоинты требуют аутентификации
- Пользователь может видеть только свои данные
- `payment_method_id` не возвращается в API (только `card_mask` и `card_brand`)

### Примеры использования (Frontend)

```typescript
// Получение информации о подписке
const response = await fetch('/api/v1/billing/subscription/', {
  headers: {
    'X-Telegram-Init-Data': initData
  }
});
const data = await response.json();

// Включение автопродления
const response = await fetch('/api/v1/billing/subscription/autorenew/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Telegram-Init-Data': initData
  },
  body: JSON.stringify({ enabled: true })
});
const updatedData = await response.json();

// Получение истории платежей
const response = await fetch('/api/v1/billing/payments/?limit=10', {
  headers: {
    'X-Telegram-Init-Data': initData
  }
});
const { results } = await response.json();
```

---

## Migration Path

### Существующие эндпоинты (совместимость)

Новые эндпоинты **не заменяют** существующие, а дополняют их:

- `GET /billing/plan` — остается для получения доступных планов
- `GET /billing/me/` — остается для получения статуса с лимитами
- `POST /billing/create-payment/` — остается для создания платежей
- `POST /billing/auto-renew/toggle` — **DEPRECATED**, используйте `/subscription/autorenew/`
- `GET /billing/payments` — **DEPRECATED**, используйте `/payments/` (с trailing slash)

### Рекомендации для фронтенда

- Используйте **новые эндпоинты** (`/subscription/`, `/payments/`) для экрана настроек
- Старые эндпоинты можно использовать для обратной совместимости
- Новые эндпоинты имеют более удобный формат для UI настроек

---

## Testing

### Запуск тестов

```bash
cd backend
python manage.py test apps.billing.tests.SubscriptionDetailsTestCase
python manage.py test apps.billing.tests.AutoRenewToggleTestCase
python manage.py test apps.billing.tests.PaymentMethodDetailsTestCase
python manage.py test apps.billing.tests.PaymentsHistoryTestCase
```

### Все тесты billing app

```bash
python manage.py test apps.billing
```
