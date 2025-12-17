# Глоссарий

## Модели

### SubscriptionPlan
Тарифный план. Определяет цену, длительность и лимиты.
- `code` — уникальный идентификатор (FREE, PRO_MONTHLY, PRO_YEARLY)
- `daily_photo_limit` — лимит фото в день (`null` = безлимит)

### Subscription
Подписка пользователя. Связь 1:1 с User.
- `plan` — текущий план
- `end_date` — дата окончания
- `auto_renew` — автопродление включено

### Payment
Платёж пользователя.
- Статусы: PENDING → SUCCEEDED / CANCELED / FAILED
- `yookassa_payment_id` — ID платежа в YooKassa

### DailyUsage
Дневное использование. Счётчик операций за день.
- Уникально по (user, date)
- `photo_ai_requests` — количество AI-запросов

### WebhookLog
Лог входящих webhook. Для идемпотентности и дебага.

---

## Термины

### Webhook
Уведомление от YooKassa о событии (payment.succeeded и т.д.).
Единственный источник истины для финансовых операций.

### Recurring payment (рекуррентный платёж)
Автоматический платёж без участия пользователя.
Использует сохранённый `payment_method_id`.

### Idempotency (идемпотентность)
Повторный запрос даёт тот же результат.
Webhook может прийти несколько раз — обработка должна быть безопасной.

### Throttle (rate limiting)
Ограничение количества запросов.
- `PaymentCreationThrottle` — 20/hour на создание платежей
- `WebhookThrottle` — 100/hour на webhook

### IP Allowlist
Список разрешённых IP для webhook.
Только IP YooKassa могут присылать webhook.

### Return URL
URL для редиректа после оплаты.
Валидируется по whitelist доменов.

### SSOT (Single Source of Truth)
Единственный источник истины.
- `SubscriptionPlan.code` — SSOT для идентификации плана
- Webhook — SSOT для статуса платежа

---

## Статусы

### Payment статусы

| Статус | Описание |
|--------|----------|
| PENDING | Ожидает оплаты |
| WAITING_FOR_CAPTURE | Ожидает подтверждения |
| SUCCEEDED | Успешно оплачен |
| CANCELED | Отменён |
| FAILED | Ошибка |
| REFUNDED | Возврат |

### WebhookLog статусы

| Статус | Описание |
|--------|----------|
| RECEIVED | Получен |
| PROCESSING | Обрабатывается |
| SUCCESS | Успешно обработан |
| FAILED | Ошибка обработки |
| DUPLICATE | Дубликат (уже обработан) |

---

## YooKassa события

| Событие | Когда |
|---------|-------|
| `payment.succeeded` | Платёж успешен |
| `payment.canceled` | Платёж отменён |
| `payment.waiting_for_capture` | Ожидает подтверждения |
| `refund.succeeded` | Возврат успешен |

---

## Сокращения

| Сокращение | Расшифровка |
|------------|-------------|
| AI | Artificial Intelligence |
| API | Application Programming Interface |
| XFF | X-Forwarded-For (HTTP header) |
| DRF | Django REST Framework |
| UUID | Universally Unique Identifier |
| HMAC | Hash-based Message Authentication Code |
