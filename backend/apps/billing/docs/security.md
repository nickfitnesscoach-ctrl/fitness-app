# Безопасность Billing

## Обзор

Модуль billing обрабатывает финансовые данные. Здесь описаны меры безопасности.

---

## Принципы

| Принцип | Реализация |
|---------|------------|
| **Цена из БД** | Сумма платежа берётся из `SubscriptionPlan.price`, не от клиента |
| **Webhook-first** | Подписка активируется только после webhook от YooKassa |
| **IP allowlist** | Webhook принимаются только с IP YooKassa |
| **Rate limiting** | Ограничение запросов на создание платежей |
| **Идемпотентность** | Защита от повторной обработки webhook |

---

## Защита платежей

### 1. Цена из БД (предотвращение fraud)

```python
# ❌ НЕЛЬЗЯ — принимать цену с фронта
amount = request.data.get("amount")

# ✅ ПРАВИЛЬНО — брать из БД
plan = SubscriptionPlan.objects.get(code=plan_code)
amount = plan.price
```

### 2. Валидация return_url (защита от open redirect)

```python
ALLOWED_DOMAINS = ["app.eatfit24.ru", "eatfit24.ru"]

def _validate_return_url(url, request):
    """Проверяет, что URL в whitelist."""
    parsed = urlparse(url)
    if parsed.netloc not in ALLOWED_DOMAINS:
        return _build_default_return_url(request)
    return url
```

### 3. Rate limiting

| Endpoint | Лимит | Класс |
|----------|-------|-------|
| `create-payment/` | 10/hour per user | `PaymentCreationThrottle` |
| `bind-card/start/` | 10/hour per user | `PaymentCreationThrottle` |
| `webhooks/yookassa` | 100/hour per IP | `WebhookThrottle` |

---

## Защита Webhook

### IP Allowlist

Webhook принимаются только с официальных IP YooKassa:

```python
YOOKASSA_IP_RANGES = [
    "185.71.76.0/27",
    "185.71.77.0/27",
    "77.75.153.0/25",
    "77.75.156.11/32",
    "77.75.156.35/32",
    "77.75.154.128/25",
    "2a02:5180::/32",  # IPv6
]
```

### XFF Protection

```python
# settings
WEBHOOK_TRUST_XFF = False  # по умолчанию не доверяем X-Forwarded-For

# Если за reverse proxy (nginx):
# WEBHOOK_TRUST_PROXIES = ["10.0.0.1"]  # IP прокси
```

### Идемпотентность

Защита от повторной обработки:

1. `WebhookLog.event_id` — уникальный ID события
2. `Payment.webhook_processed_at` — метка обработки
3. Проверка статуса перед изменением

```python
if payment.status in ("SUCCEEDED", "REFUNDED"):
    logger.info("Already processed, skipping")
    return
```

---

## Атомарность лимитов

### Race condition protection

```python
@transaction.atomic
def increment_usage(user, date, feature):
    usage, _ = DailyUsage.objects.select_for_update().get_or_create(...)
    usage.count = F('count') + 1
    usage.save()
```

---

## Admin-only endpoints

| Endpoint | Проверка |
|----------|----------|
| `create-test-live-payment/` | `user.is_staff` |

---

## Чек-лист безопасности

- [x] Цена берётся из БД, не от клиента
- [x] return_url валидируется по whitelist
- [x] Webhook проверяет IP
- [x] Rate limiting на платежах
- [x] Идемпотентность webhook
- [x] XFF protection по умолчанию
- [x] Атомарные операции с лимитами
- [x] Тестовые планы скрыты от обычных пользователей

---

## Что делать, если YooKassa шлёт мусор

### Сценарии "мусора"

| Проблема | Как обрабатываем |
|----------|------------------|
| Неизвестный `event_type` | Логируем, возвращаем 200 OK |
| Отсутствует `object.id` | Логируем ошибку, 200 OK |
| `payment_id` не найден в БД | Логируем warning, 200 OK |
| Дублирующий webhook | Идемпотентность — пропускаем |
| Невалидный JSON | 400 Bad Request |
| IP не в allowlist | 403 Forbidden, логируем |

### Принцип

> ⚠️ ВСЕГДА возвращай 200 OK (кроме 400/403), иначе YooKassa будет ретраить.

---

## Чек-лист продакшн деплоя биллинга

- [ ] `YOOKASSA_SHOP_ID` и `YOOKASSA_SECRET_KEY` заданы (production)
- [ ] `BILLING_RECURRING_ENABLED` = true/false (осознанно)
- [ ] Webhook URL зарегистрирован в кабинете YooKassa
- [ ] IP allowlist актуален (проверить https://yookassa.ru/developers/api)
- [ ] Rate limiting включён (`PaymentCreationThrottle`, `WebhookThrottle`)
- [ ] XFF protection = `WEBHOOK_TRUST_XFF=false` (или настроен прокси)
- [ ] Celery worker запущен с очередью `-Q billing`
- [ ] Celery beat запущен (для retry_stuck_webhooks)
- [ ] `TELEGRAM_ADMINS` настроен для алертов
- [ ] Тестовый платёж прошёл успешно
- [ ] Проверена идемпотентность (повторный webhook не дублирует)
