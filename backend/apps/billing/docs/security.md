# Безопасность Billing

## Обзор

Billing — критический модуль, работающий с деньгами. Применяется многоуровневая защита.

## Принципы

### 1. Цена из БД, не от клиента

```python
# ❌ НИКОГДА
amount = request.data.get("amount")

# ✅ ВСЕГДА
plan = SubscriptionPlan.objects.get(code=plan_code)
amount = plan.price
```

### 2. Webhook = источник истины

```python
# ❌ НЕЛЬЗЯ доверять фронту
if frontend_says_success:
    subscription.extend()

# ✅ ТОЛЬКО после webhook
def _handle_payment_succeeded(payload):
    payment.mark_as_succeeded()
    activate_or_extend_subscription(...)
```

### 3. Атомарные лимиты

```python
# ❌ Race condition
if usage.count < limit:
    usage.count += 1

# ✅ Атомарно
allowed, new_count = DailyUsage.objects.check_and_increment_if_allowed(
    user=user, limit=limit, amount=1
)
```

## Rate Limiting (Throttling)

### PaymentCreationThrottle

- **Scope:** `billing_create_payment`
- **Rate:** 20/hour
- **Key:** user_id (авторизован) или IP

Защищает от:
- Спама платежей
- DoS на создание Payment
- Мусора в БД

### WebhookThrottle

- **Scope:** `billing_webhook`
- **Rate:** 100/hour
- **Key:** IP адрес

Защищает от:
- Флудинга webhook endpoint
- Попыток перебора

## IP Allowlist (Webhooks)

Webhook принимается **только** с IP YooKassa:

```python
YOOKASSA_IP_RANGES = [
    "185.71.76.0/27",
    "185.71.77.0/27",
    "77.75.153.0/25",
    "77.75.156.11/32",
    "77.75.156.35/32",
    "77.75.154.128/25",
    "2a02:5180::/32",
]
```

### XFF Spoofing Protection

По умолчанию `WEBHOOK_TRUST_XFF=False`:
- Используется `REMOTE_ADDR`
- X-Forwarded-For игнорируется

Если за reverse proxy (Nginx):
```
WEBHOOK_TRUST_XFF=True
```

## Return URL Validation

Защита от Open Redirect:

```python
ALLOWED_RETURN_URL_DOMAINS = ["eatfit24.ru", "app.eatfit24.ru"]
```

Если `return_url` не в whitelist — используется дефолтный.

## Test Plans Protection

Тестовые планы (`is_test=True`) недоступны через обычный API:

```python
plans = SubscriptionPlan.objects.filter(is_active=True, is_test=False)
```

Только через специальный endpoint для админов.

## Идемпотентность

### Webhook deduplication

1. `WebhookLog.event_id` — логируем каждое событие
2. `Payment.webhook_processed_at` — метка обработки
3. Проверка статуса перед изменением

### Payment creation

UUID idempotency_key при создании платежа в YooKassa.

## Настройки безопасности

```python
# settings.py

# Доверять X-Forwarded-For в webhooks
WEBHOOK_TRUST_XFF = False

# Разрешённые домены для return_url
ALLOWED_RETURN_URL_DOMAINS = ["eatfit24.ru", "app.eatfit24.ru"]

# Дефолтный return_url
YOOKASSA_RETURN_URL = "https://app.eatfit24.ru/subscription"

# Throttle rates
REST_FRAMEWORK = {
    "DEFAULT_THROTTLE_RATES": {
        "billing_create_payment": "20/hour",
        "billing_webhook": "100/hour",
    }
}
```

## Чеклист безопасности

| Проверка | Статус |
|----------|--------|
| Цена из БД | ✅ |
| Webhook валидация IP | ✅ |
| XFF spoofing защита | ✅ |
| Rate limiting | ✅ |
| Атомарные лимиты | ✅ |
| Return URL whitelist | ✅ |
| Test plans фильтрация | ✅ |
| Идемпотентность | ✅ |

## Оставшиеся рекомендации

1. **HMAC-проверка webhook** — YooKassa поддерживает подписи
2. **unique=True на WebhookLog.event_id** — DB-level защита от дублей
3. **Тесты на throttling** — автоматическая проверка
