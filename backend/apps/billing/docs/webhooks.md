# Webhooks

## Обзор

Webhook — **единственный источник истины** для финансовых операций.

Платёж считается успешным **только после** получения `payment.succeeded` от YooKassa.

## Endpoint

```
POST /api/v1/billing/webhooks/yookassa
```

- Публичный (AllowAny)
- Защищён IP allowlist + rate limiting
- Всегда возвращает `200 OK` (если запрос валиден)

## Архитектура

```
webhooks/
├── views.py      # Приём, валидация, идемпотентность
├── handlers.py   # Бизнес-логика событий
└── utils.py      # IP allowlist
```

### views.py

1. Проверяет IP клиента
2. Парсит JSON
3. Проверяет идемпотентность (WebhookLog)
4. Вызывает handler
5. Возвращает 200 OK

### handlers.py

Обрабатывает события:
- `payment.succeeded` — платёж успешен
- `payment.canceled` — платёж отменён
- `payment.waiting_for_capture` — ожидание подтверждения
- `refund.succeeded` — возврат успешен

### utils.py

IP allowlist YooKassa:
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

## События

### payment.succeeded

**Что делает:**
1. Находит `Payment` по `yookassa_payment_id`
2. Проверяет, что ещё не обработан (`webhook_processed_at`)
3. Помечает `SUCCEEDED`
4. Сохраняет `payment_method_id` (для автопродления)
5. Продлевает подписку
6. Обновляет данные карты в `Subscription`
7. Инвалидирует кеш

### payment.canceled

**Что делает:**
1. Находит `Payment`
2. Если не `SUCCEEDED`/`REFUNDED` — помечает `CANCELED`

### refund.succeeded

**Что делает:**
1. Создаёт/обновляет `Refund`
2. Помечает `Payment` как `REFUNDED`

## Идемпотентность

YooKassa может слать один webhook несколько раз.

Защита:
1. `WebhookLog.event_id` — уникальный ID события
2. `Payment.webhook_processed_at` — метка обработки
3. Проверка статуса перед изменением

```python
# Пример: не обрабатываем повторно
if payment.status in ("SUCCEEDED", "REFUNDED"):
    logger.info("Payment already processed, skipping")
    return
```

## Логирование

Каждый webhook логируется в `WebhookLog`:
- `event_type` — тип события
- `event_id` — ID события YooKassa
- `raw_payload` — полный payload
- `client_ip` — IP отправителя
- `status` — результат обработки

## Безопасность

| Мера | Реализация |
|------|------------|
| IP allowlist | `utils.is_ip_allowed()` |
| Rate limiting | `WebhookThrottle` (100/hour) |
| XFF защита | `WEBHOOK_TRUST_XFF=False` по умолчанию |
| Идемпотентность | `WebhookLog` + `webhook_processed_at` |

## Troubleshooting

### Платёж прошёл, подписка не обновилась

1. Проверь `WebhookLog` — дошёл ли webhook?
2. Проверь `Payment.webhook_processed_at` — обработан?
3. Проверь логи сервера — есть ли ошибки?
4. Проверь IP — разрешён ли в allowlist?

### Дублирующиеся события

Нормально. Идемпотентность обеспечена.

### Webhook не доходит

1. Проверь URL в настройках YooKassa
2. Проверь IP allowlist (мог измениться)
3. Проверь firewall/nginx
