# Поток платежа

## Обзор

Платёж в EatFit24 — это **webhook-first** процесс:

```
1. Фронт → POST /billing/create-payment/
2. Бэкенд → создаёт Payment + вызывает YooKassa
3. Пользователь → оплачивает на YooKassa
4. YooKassa → POST /billing/webhooks/yookassa
5. Бэкенд → обновляет подписку + отправляет уведомление
```

> ⚠️ **Важно:** подписка обновляется ТОЛЬКО после webhook!

---

## Шаги

### 1. Запрос планов

```
GET /api/v1/billing/plans/
```

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
{
  "plan_code": "PRO_MONTHLY"
}
```

**Бэкенд:**
1. Проверяет `plan_code` в БД
2. Берёт `price` **из БД** (не от клиента!)
3. Создаёт `Payment` со статусом `PENDING`
4. Вызывает `YooKassaService.create_payment()`

```json
{
  "confirmation_url": "https://yoomoney.ru/checkout/...",
  "payment_id": "uuid..."
}
```

### 3. Оплата пользователем

Фронт редиректит на `confirmation_url`.

> ⚠️ Возврат на `return_url` **НЕ означает успех платежа!**

### 4. Webhook от YooKassa

```
POST /api/v1/billing/webhooks/yookassa
```

**Бэкенд:**
1. Проверяет IP (allowlist YooKassa)
2. Логирует в `WebhookLog`
3. Ставит Celery task на обработку
4. Возвращает 200 OK

**Celery task:**
1. Находит `Payment` по `yookassa_payment_id`
2. Помечает `Payment.status = SUCCEEDED`
3. Вызывает `activate_or_extend_subscription()`
4. Отправляет Telegram-уведомление админам
5. Инвалидирует кеш плана

### 5. Проверка статуса

```
GET /api/v1/billing/me/
```

```json
{
  "plan_code": "PRO_MONTHLY",
  "plan_name": "PRO месячный",
  "is_active": true,
  "end_date": "2025-01-17T14:00:00Z"
}
```

---

## Статусы Payment

```
PENDING → SUCCEEDED (webhook payment.succeeded)
PENDING → CANCELED (webhook payment.canceled)
PENDING → WAITING_FOR_CAPTURE (редко)
SUCCEEDED → REFUNDED (webhook refund.succeeded)
```

---

## Правила

| ❌ Нельзя | ✅ Нужно |
|----------|---------|
| Принимать сумму с фронта | Брать цену из `SubscriptionPlan.price` |
| Считать успешным по return_url | Ждать webhook |
| Менять подписку без webhook | Обновлять только в handlers.py |

---

## Автопродление

Если `BILLING_RECURRING_ENABLED=true`:

1. При оплате сохраняется `payment_method_id`
2. Command `process_recurring_payments` создаёт рекуррентный платёж
3. Webhook обрабатывается так же
