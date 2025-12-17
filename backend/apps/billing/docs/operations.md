# Эксплуатация Billing

## Management Commands

### cleanup_expired_subscriptions

**Назначение:** Переводит истёкшие платные подписки на FREE.

**Запуск:**
```bash
python manage.py cleanup_expired_subscriptions
```

**Параметры:**
- `--dry-run` — показать, что будет сделано, без изменений
- `--batch-size=100` — размер батча обработки
- `--grace-days=0` — дополнительные дни после истечения

**Что делает:**
1. Находит подписки с `end_date < now()` и `plan ≠ FREE`
2. Переводит на план FREE
3. Отключает `auto_renew`
4. Сохраняет `is_active = True`

**Рекомендуемое расписание:** Ежедневно в 00:05

```cron
5 0 * * * cd /app && python manage.py cleanup_expired_subscriptions
```

---

### process_recurring_payments

**Назначение:** Создаёт рекуррентные платежи для подписок с автопродлением.

**Запуск:**
```bash
python manage.py process_recurring_payments
```

**Параметры:**
- `--dry-run` — показать, что будет сделано
- `--days-before=3` — за сколько дней до истечения создавать платёж

**Что делает:**
1. Находит подписки: `auto_renew=True`, истекают в ближайшие N дней
2. Для каждой создаёт рекуррентный платёж в YooKassa
3. Использует сохранённый `payment_method_id`
4. Логирует результат

**Рекомендуемое расписание:** Ежедневно в 10:00

```cron
0 10 * * * cd /app && python manage.py process_recurring_payments --days-before=3
```

---

## Мониторинг

### Ключевые метрики

| Метрика | Источник | Алерт |
|---------|----------|-------|
| Успешные платежи | `Payment.status=SUCCEEDED` | — |
| Неудачные платежи | `Payment.status=FAILED` | > 10% от общего |
| Webhook ошибки | `WebhookLog.status=FAILED` | Любые |
| Истёкшие подписки | `Subscription` где `end_date < now` | > 100 необработанных |

### Логи

```python
# Ключевые логгеры
logging.getLogger("apps.billing.views")
logging.getLogger("apps.billing.services")
logging.getLogger("apps.billing.webhooks")
```

### Алерты

1. **Webhook не доходят** — нет новых `WebhookLog` за час при активных платежах
2. **Массовые отказы** — > 10 платежей FAILED за час
3. **Автопродление не работает** — нет рекуррентных платежей неделю

---

## Troubleshooting

### Платёж прошёл, подписка не продлилась

1. Проверь `Payment`:
   ```sql
   SELECT * FROM payments WHERE yookassa_payment_id = 'xxx';
   ```
   - `status` должен быть `SUCCEEDED`
   - `webhook_processed_at` должен быть заполнен

2. Проверь `WebhookLog`:
   ```sql
   SELECT * FROM webhook_logs WHERE payment_id = 'xxx' ORDER BY created_at DESC;
   ```
   - `status` должен быть `SUCCESS`

3. Проверь логи:
   ```bash
   grep "payment.succeeded" /var/log/app/*.log | grep "xxx"
   ```

### Webhook возвращает 403

1. IP не в allowlist — обновить `YOOKASSA_IP_RANGES`
2. XFF spoofing — проверить `WEBHOOK_TRUST_XFF`

### Рекуррентный платёж не создаётся

1. Проверь `Subscription.auto_renew` — должен быть `True`
2. Проверь `Subscription.yookassa_payment_method_id` — должен быть заполнен
3. Проверь логи команды:
   ```bash
   python manage.py process_recurring_payments --dry-run
   ```

### Лимиты не работают

1. Проверь `DailyUsage`:
   ```sql
   SELECT * FROM billing_dailyusage WHERE user_id = X AND date = CURDATE();
   ```

2. Проверь `SubscriptionPlan.daily_photo_limit`:
   ```sql
   SELECT code, daily_photo_limit FROM subscription_plans;
   ```

---

## Резервное копирование

**Критические таблицы:**
- `subscription_plans` — тарифы
- `subscriptions` — подписки пользователей
- `payments` — платежи

**Резервное копирование:**
```bash
pg_dump -t subscription_plans -t subscriptions -t payments > billing_backup.sql
```

---

## Обновление IP YooKassa

Если YooKassa изменит IP-диапазоны:

1. Обнови `webhooks/utils.py`:
   ```python
   YOOKASSA_IP_RANGES = [
       # новые диапазоны
   ]
   ```

2. Перезапусти backend:
   ```bash
   docker-compose restart backend
   ```

3. Проверь, что webhooks доходят

---

## Полезные команды

```bash
# Статус подписок
python manage.py shell -c "
from apps.billing.models import Subscription
print('Active PRO:', Subscription.objects.filter(plan__code__startswith='PRO', is_active=True).count())
print('Expired:', Subscription.objects.filter(end_date__lt=timezone.now()).exclude(plan__code='FREE').count())
"

# Последние платежи
python manage.py shell -c "
from apps.billing.models import Payment
for p in Payment.objects.order_by('-created_at')[:10]:
    print(f'{p.created_at} | {p.status} | {p.amount}₽ | {p.user.email}')
"

# Последние webhooks
python manage.py shell -c "
from apps.billing.models import WebhookLog
for w in WebhookLog.objects.order_by('-created_at')[:10]:
    print(f'{w.created_at} | {w.event_type} | {w.status}')
"
```
