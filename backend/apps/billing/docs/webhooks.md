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
- Защищён IP allowlist + rate limiting
- Всегда возвращает `200 OK`

---

## Архитектура

```
webhooks/
├── views.py      # Приём, валидация, логирование
├── handlers.py   # Бизнес-логика событий
├── tasks.py      # Celery tasks (async обработка)
└── utils.py      # IP allowlist
```

### Поток обработки

```
1. views.py: приём запроса, валидация IP
2. views.py: логирование в WebhookLog
3. views.py: постановка Celery task
4. views.py: return 200 OK
5. tasks.py: async обработка
6. handlers.py: бизнес-логика
7. notifications.py: Telegram-уведомление (если PRO)
```

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

## IP Allowlist

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

---

## Идемпотентность

YooKassa может слать один webhook несколько раз.

**Защита:**
1. `WebhookLog.event_id` — уникальный ID события
2. `Payment.webhook_processed_at` — метка обработки
3. Проверка статуса перед изменением

```python
if payment.status in ("SUCCEEDED", "REFUNDED"):
    logger.info("Already processed, skipping")
    return
```

---

## Логирование

Каждый webhook логируется в `WebhookLog`:

| Поле | Описание |
|------|----------|
| `event_type` | Тип события |
| `event_id` | ID события YooKassa |
| `raw_payload` | Полный payload |
| `client_ip` | IP отправителя |
| `status` | Результат обработки |

---

## Celery Tasks

| Task | Описание |
|------|----------|
| `process_yookassa_webhook` | Обработка одного webhook |
| `retry_stuck_webhooks` | Повтор зависших (PROCESSING >10 мин) |
| `alert_failed_webhooks` | Alert о failed за час |

**Retry strategy:**
- max_retries=5
- Экспоненциальный backoff: 30s, 60s, 120s, 240s, 480s
- ack_late=True (подтверждение после обработки)

---

## Troubleshooting

### Платёж прошёл, подписка не обновилась

1. Проверь `WebhookLog` — дошёл ли webhook?
2. Проверь `Payment.webhook_processed_at` — обработан?
3. Проверь логи celery worker — есть ли ошибки?

### Webhook не доходит

1. Проверь URL в настройках YooKassa
2. Проверь IP allowlist (мог измениться)
3. Проверь firewall/nginx
