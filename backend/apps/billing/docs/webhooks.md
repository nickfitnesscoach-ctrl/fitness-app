# Webhooks

## Обзор

Webhook — **единственный источник истины** для финансовых операций.

Платёж считается успешным **только после** получения `payment.succeeded` от YooKassa.

---

## Endpoint

```
POST /api/v1/billing/webhooks/yookassa
```

- Публичный (AllowAny)
- Защищён IP allowlist + XFF guard + rate limiting
- Всегда возвращает `200 OK`

---

## Архитектура

```
webhooks/
├── views.py      # Приём, валидация, trace_id, логирование
├── handlers.py   # Бизнес-логика событий
├── tasks.py      # Celery tasks (async обработка, queue=billing)
└── utils.py      # IP allowlist
```

### Поток обработки

```
1. views.py: генерация trace_id
2. views.py: XFF security check (_get_client_ip_secure)
3. views.py: валидация IP allowlist
4. views.py: extract provider_event_id (idempotency)
5. views.py: WebhookLog.get_or_create (UNIQUE constraint)
6. views.py: sanitize payload (redact card details)
7. views.py: enqueue Celery task → queue='billing'
8. views.py: return 200 OK
9. tasks.py: process_yookassa_webhook (trace_id propagated)
10. handlers.py: бизнес-логика
11. notifications.py: Telegram-уведомление (если PRO)
```

---

## Observability (trace_id)

Каждый webhook получает уникальный `trace_id` (8 символов) для корреляции логов:

| Log Message | Точка |
|-------------|-------|
| `[WEBHOOK_RECEIVED] trace_id=...` | Вход |
| `[WEBHOOK_BLOCKED] trace_id=...` | IP не в allowlist |
| `[WEBHOOK_DUPLICATE] trace_id=...` | Повторный webhook |
| `[WEBHOOK_QUEUED] trace_id=... task_id=...` | Enqueue |
| `[WEBHOOK_TASK_START] trace_id=...` | Task start |
| `[WEBHOOK_TASK_DONE] trace_id=... ok=true/false` | Task done |

---

## События

### payment.succeeded

**Что делает handler:**
1. Находит `Payment` по `yookassa_payment_id`
2. Проверяет идемпотентность (не обработан ли уже)
3. Помечает `SUCCEEDED`
4. Сохраняет `payment_method_id` (для автопродления)
5. Продлевает подписку
6. Обновляет данные карты в `Subscription`
7. **Отправляет Telegram-уведомление** админам
8. Инвалидирует кеш

### payment.canceled

1. Находит `Payment`
2. Если не `SUCCEEDED`/`REFUNDED` — помечает `CANCELED`

### refund.succeeded

1. Создаёт/обновляет `Refund`
2. Помечает `Payment` как `REFUNDED`

---

## Security

### IP Allowlist

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

### XFF Trust Guard (A2)

```python
# XFF доверяется ТОЛЬКО если REMOTE_ADDR ∈ WEBHOOK_TRUSTED_PROXIES
if trust_xff and _is_trusted_proxy(remote_addr):
    real_ip = xff.split(",")[0].strip()
else:
    real_ip = remote_addr  # Ignore spoofed XFF
```

**Settings:**
- `WEBHOOK_TRUST_XFF=True` — включить доверие к XFF
- `WEBHOOK_TRUSTED_PROXIES=172.24.0.0/16` — Docker сеть

---

## Идемпотентность (A3)

### Два уровня защиты:

1. **DB level:** `WebhookLog.event_id` — UNIQUE constraint
2. **Business level:** `Payment.status` check

### event_id приоритет:

1. `provider_event_id` — YooKassa UUID из payload (primary)
2. Fallback: `{event_type}:{obj_id}:{obj_status}`

```python
# WebhookLog model
provider_event_id = CharField(null=True, db_index=True)  # YooKassa native ID
event_id = CharField(unique=True)  # Idempotency key
```

---

## Celery Queue (A5)

```python
# config/celery.py
app.conf.task_routes = {
    "apps.billing.webhooks.tasks.*": {"queue": "billing"},
    "apps.billing.tasks_recurring.*": {"queue": "billing"},
}
```

**Worker MUST run with:** `-Q ai,billing,default`

### Tasks

| Task | Queue | Описание |
|------|-------|----------|
| `process_yookassa_webhook` | billing | Обработка webhook |
| `retry_stuck_webhooks` | billing | Retry зависших (>10 мин) |
| `alert_failed_webhooks` | billing | Alert о failed |

**Retry strategy:**
- max_retries=5
- Экспоненциальный backoff: 30s → 480s
- ack_late=True

---

## Payload Sanitization (P2-1)

Sensitive card data redacted before storage:

```python
# Removed: first6, expiry_month, expiry_year
# Kept: id, type, saved, card.last4
"payment_method": {"id": "...", "card": {"last4": "1234", "redacted": True}}
```

---

## WebhookLog Model

| Поле | Описание |
|------|----------|
| `event_type` | Тип события |
| `event_id` | Idempotency key (UNIQUE) |
| `provider_event_id` | YooKassa native ID |
| `trace_id` | Request correlation ID |
| `raw_payload` | Sanitized payload |
| `client_ip` | IP отправителя |
| `status` | RECEIVED/QUEUED/PROCESSING/SUCCESS/FAILED/DUPLICATE |

---

## Troubleshooting

### Платёж прошёл, подписка не обновилась

1. Проверь `WebhookLog.trace_id` — найди цепочку
2. Проверь `WebhookLog.status` — дошёл ли webhook?
3. Проверь Celery logs: `grep trace_id`
4. Проверь `Payment.webhook_processed_at`

### Webhook не доходит (403)

1. Проверь WEBHOOK_TRUST_XFF=true
2. Проверь WEBHOOK_TRUSTED_PROXIES содержит Docker subnet
3. Проверь логи: `grep WEBHOOK_BLOCKED`

### Worker не обрабатывает

1. Проверь очереди: `celery inspect active_queues | grep billing`
2. Worker должен запускаться с `-Q ai,billing,default`

---

## 🚫 ЗАПРЕЩЕНО для handlers.py

- ❌ Делать HTTP запросы
- ❌ Читать `request` объект
- ❌ Поднимать exceptions наружу
- ❌ Менять статус WebhookLog на SUCCESS до завершения

---

## SLA обработки

| Метрика | Значение | Алерт |
|---------|----------|-------|
| Webhook → QUEUED | < 1 сек | — |
| QUEUED → SUCCESS | < 30 сек | > 1 мин |
| PROCESSING зависший | > 10 мин | retry_stuck_webhooks |
| FAILED за час | > 5 | alert_failed_webhooks |
