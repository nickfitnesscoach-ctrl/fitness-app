# Поток платежа

## Обзор

Платёж в EatFit24 — это **webhook-first** процесс:
1. Фронт инициирует платёж
2. Бэкенд создаёт платёж в YooKassa
3. Пользователь оплачивает на стороне YooKassa
4. YooKassa присылает webhook
5. **Только после webhook** подписка обновляется

## Шаги

### 1. Запрос планов

```
GET /api/v1/billing/plans/
```

Возвращает активные планы (без `is_test=True`):

```json
[
  {
    "code": "PRO_MONTHLY",
    "display_name": "PRO месячный",
    "price": "299.00",
    "duration_days": 30,
    "features": {...}
  }
]
```

### 2. Создание платежа

```
POST /api/v1/billing/create-payment/
Content-Type: application/json

{
  "plan_code": "PRO_MONTHLY",
  "return_url": "https://app.eatfit24.ru/subscription"  // optional
}
```

**Бэкенд делает:**
1. Проверяет `plan_code` в БД
2. Берёт `price` **из БД** (не от клиента!)
3. Создаёт локальный `Payment` со статусом `PENDING`
4. Вызывает `YooKassaService.create_payment()`
5. Возвращает `confirmation_url`

```json
{
  "confirmation_url": "https://yoomoney.ru/checkout/...",
  "payment_id": "uuid..."
}
```

### 3. Оплата пользователем

Фронт редиректит на `confirmation_url`.
Пользователь вводит данные карты на YooKassa.
После оплаты — возврат на `return_url`.

> ⚠️ Возврат на `return_url` **не означает успех платежа!**

### 4. Webhook от YooKassa

```
POST /api/v1/billing/webhooks/yookassa
```

YooKassa присылает событие:

```json
{
  "type": "notification",
  "event": "payment.succeeded",
  "object": {
    "id": "yookassa-payment-id",
    "status": "succeeded",
    "payment_method": {
      "id": "pm_...",
      "card": {
        "last4": "1234",
        "card_type": "Visa"
      }
    }
  }
}
```

**Бэкенд делает:**
1. Проверяет IP (allowlist YooKassa)
2. Проверяет идемпотентность (WebhookLog)
3. Находит `Payment` по `yookassa_payment_id`
4. Помечает `Payment.status = SUCCEEDED`
5. Вызывает `activate_or_extend_subscription()`
6. Сохраняет `payment_method_id` для автопродления
7. Инвалидирует кеш плана

### 5. Проверка статуса

Фронт после возврата проверяет:

```
GET /api/v1/billing/me/
```

```json
{
  "plan_code": "PRO_MONTHLY",
  "plan_name": "PRO месячный",
  "is_active": true,
  "end_date": "2025-01-17T14:00:00Z",
  "daily_photo_limit": null,
  "used_today": 5
}
```

## Статусы Payment

```
PENDING → SUCCEEDED (webhook payment.succeeded)
PENDING → CANCELED (webhook payment.canceled)
PENDING → WAITING_FOR_CAPTURE (редко)
SUCCEEDED → REFUNDED (webhook refund.succeeded)
```

## Принципы

| ❌ Нельзя | ✅ Нужно |
|----------|---------|
| Принимать сумму с фронта | Брать цену из `SubscriptionPlan.price` |
| Считать платёж успешным по return_url | Ждать webhook |
| Менять подписку без webhook | Обновлять только в handlers.py |
| Доверять `confirmation_url` статусу | Проверять `Payment.status` |

## Автопродление

Если `save_payment_method=True`:
1. При успешном платеже сохраняется `payment_method_id`
2. Management command `process_recurring_payments` использует его
3. Создаётся рекуррентный платёж без участия пользователя
4. Webhook обрабатывается так же
