# Эксплуатация Billing

## Celery Tasks

### Очередь `billing`

Billing использует отдельную Celery очередь для изоляции от AI задач.

```python
# celery worker для billing
celery -A config.celery_app worker -Q billing --loglevel=info
```

### Задачи

| Task | Описание | Schedule |
|------|----------|----------|
| `process_yookassa_webhook` | Обработка webhook | По событию |
| `retry_stuck_webhooks` | Повтор зависших webhook | Каждые 5 мин |
| `alert_failed_webhooks` | Alert о failed webhook | Каждые 15 мин |
| `cleanup_pending_payments` | Очистка PENDING >24ч | Каждый час |

### Celery Beat конфиг

```python
CELERY_BEAT_SCHEDULE = {
    'retry-stuck-webhooks': {
        'task': 'apps.billing.webhooks.tasks.retry_stuck_webhooks',
        'schedule': crontab(minute='*/5'),
    },
    'alert-failed-webhooks': {
        'task': 'apps.billing.webhooks.tasks.alert_failed_webhooks',
        'schedule': crontab(minute='*/15'),
    },
    'cleanup-pending-payments': {
        'task': 'apps.billing.webhooks.tasks.cleanup_pending_payments',
        'schedule': crontab(minute=0),  # каждый час
    },
}
```

---

## Management Commands

### process_recurring_payments

Обработка автопродлений подписок:

```bash
python manage.py process_recurring_payments
```

### cleanup_expired_subscriptions

Перевод истёкших подписок на FREE:

```bash
python manage.py cleanup_expired_subscriptions
```

---

## Мониторинг

### Логи

```bash
# Все billing логи
docker logs eatfit24-backend-1 2>&1 | grep "\[BILLING\]"

# Webhook логи
docker logs eatfit24-celery-worker-1 2>&1 | grep "\[WEBHOOK"
```

### Проверка webhook доставки

```sql
-- Последние 10 webhook
SELECT event_type, status, created_at 
FROM webhook_logs 
ORDER BY created_at DESC 
LIMIT 10;

-- Failed за последний час
SELECT COUNT(*) 
FROM webhook_logs 
WHERE status = 'FAILED' 
AND created_at > NOW() - INTERVAL '1 hour';
```

### Проверка платежей

```sql
-- PENDING платежи старше часа (возможно проблема)
SELECT id, amount, created_at 
FROM payments 
WHERE status = 'PENDING' 
AND created_at < NOW() - INTERVAL '1 hour';
```

---

## Troubleshooting

### Платёж прошёл, подписка не обновилась

1. Проверь `webhook_logs` — дошёл ли webhook?
2. Проверь `payments.webhook_processed_at` — обработан?
3. Проверь логи celery worker — есть ли ошибки?
4. Проверь IP — разрешён ли в allowlist?

```sql
SELECT * FROM webhook_logs 
WHERE payment_id = 'xxx' 
ORDER BY created_at DESC;
```

### Webhook не доходит

1. Проверь URL в настройках YooKassa
2. Проверь firewall/nginx — пропускает ли POST?
3. Проверь IP allowlist — не изменился ли?

### Recurring 403 Forbidden

**Причина:** recurring не активирован в YooKassa

**Решение:**
1. Активировать recurring в кабинете YooKassa
2. Установить `BILLING_RECURRING_ENABLED=true`
3. Перезапустить backend

---

## Telegram Алерты

### Настройка

```env
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_ADMINS=123456789,987654321
```

### Какие алерты приходят

| Событие | Сообщение |
|---------|-----------|
| Новая PRO подписка | 🎉 НОВАЯ ПОДПИСКА PRO |
| Failed webhooks | 🚨 BILLING ALERT |
| Много отменённых платежей | ⚠️ BILLING CLEANUP |

---

## Переключатель Recurring

### Текущий статус

Проверить:
```bash
docker exec eatfit24-backend-1 python -c "from django.conf import settings; print(settings.BILLING_RECURRING_ENABLED)"
```

### Как переключить

1. Изменить в `.env`:
   ```env
   BILLING_RECURRING_ENABLED=true  # или false
   ```

2. Перезапустить:
   ```bash
   docker compose restart backend celery-worker
   ```

| Режим | save_payment_method | Автопродление |
|-------|---------------------|---------------|
| `true` | ✅ да | ✅ доступно |
| `false` | ❌ нет | ❌ недоступно |
