# Переключатель режимов оплаты (Recurring / One-Time)

## Проблема

ЮKassa вернула ошибку **403 Forbidden** при попытке создания платежа с `save_payment_method=true`. Это означает, что на аккаунте либо:
- Не включена функция рекуррентных платежей
- Не завершена настройка recurring в личном кабинете ЮKassa
- Аккаунт находится в тестовом режиме без рекуррентов

## Решение

Внедрён **двухрежимный биллинг**:
- **ONE_TIME** режим — единоразовые платежи без сохранения карты
- **RECURRING** режим — платежи с сохранением карты для автопродления

Переключение режимов происходит через единый флаг `BILLING_RECURRING_ENABLED` в `.env`.

---

## Как это работает

### 1. Флаг в .env

Добавьте в `/opt/EatFit24/.env`:

```bash
# false = ONE_TIME режим (без recurring полей)
# true = RECURRING режим (с save_payment_method)
BILLING_RECURRING_ENABLED=false
```

**Важно:**
- По умолчанию `false` (безопасный режим)
- Когда ЮKassa включит recurring → измените на `true`

### 2. Логика построения payload

Вся логика в одной функции: `build_yookassa_payment_payload()` в [services.py:49](../services.py#L49)

**ONE_TIME режим (BILLING_RECURRING_ENABLED=false):**
```python
{
    "amount": {"value": "990.00", "currency": "RUB"},
    "confirmation": {"type": "redirect", "return_url": "..."},
    "capture": True,
    "description": "Подписка PRO",
    "metadata": {
        "payment_id": "...",
        "user_id": "...",
        "plan_code": "PRO_MONTHLY",
        "billing_mode": "ONE_TIME"  # маркер режима
    }
    # НЕТ save_payment_method
    # НЕТ payment_method_data
    # НЕТ merchant_customer_id
}
```

**RECURRING режим (BILLING_RECURRING_ENABLED=true):**
```python
{
    "amount": {"value": "990.00", "currency": "RUB"},
    "confirmation": {"type": "redirect", "return_url": "..."},
    "capture": True,
    "description": "Подписка PRO",
    "save_payment_method": True,  # ДОБАВЛЕНО
    "metadata": {
        "payment_id": "...",
        "user_id": "...",
        "plan_code": "PRO_MONTHLY",
        "billing_mode": "RECURRING"  # маркер режима
    }
}
```

### 3. Сохранение режима в БД

При создании `Payment` в `metadata` добавляется `billing_mode`:

```python
payment.metadata = {
    "plan_code": plan.code,
    "amount": str(plan.price),
    "billing_mode": "ONE_TIME"  # или "RECURRING"
}
```

**Зачем:** В логах webhook и в админке видно, в каком режиме был создан платёж.

### 4. Обработка ошибок

Если ЮKassa вернёт **403 Forbidden**, API вернёт:

```json
{
    "error": {
        "code": "YOOKASSA_FORBIDDEN",
        "message": "Платёжная система временно недоступна. Попробуйте позже или свяжитесь с поддержкой."
    }
}
```

**HTTP статус:** 403 (не 502)

**Места обработки:**
- [views.py:542-552](../views.py#L542-L552) — `create_payment`
- [views.py:623-632](../views.py#L623-L632) — `bind_card_start`
- [views.py:727-733](../views.py#L727-L733) — `create_test_live_payment`

---

## Как включить рекурренты обратно

Когда ЮKassa включит recurring в вашем аккаунте:

### Шаг 1: Измените флаг

```bash
# В /opt/EatFit24/.env
BILLING_RECURRING_ENABLED=true
```

### Шаг 2: Перезапустите сервисы

```bash
cd /opt/EatFit24
docker compose restart backend celery-worker
```

### Шаг 3: Проверьте логи

```bash
docker logs -f backend --tail=50
```

Должны увидеть:
```
Built YooKassa payload: mode=RECURRING, save_payment_method=True, amount=990.00
```

### Шаг 4: Тест

1. Создайте платёж через Mini App
2. Проверьте, что:
   - Платёж создался (нет 403)
   - В метаданных `billing_mode=RECURRING`
   - После оплаты webhook пришёл и подписка продлилась

---

## Что изменилось в коде

### Файлы

1. **.env.example** — добавлен флаг `BILLING_RECURRING_ENABLED`
2. **services.py** — функция `build_yookassa_payment_payload()` (централизованная сборка payload)
3. **services.py** — `YooKassaService.create_payment()` теперь использует билдер
4. **services.py** — `create_subscription_payment()` сохраняет `billing_mode` в metadata
5. **views.py** — улучшена обработка ошибок (403 → понятный JSON, не 502)

### Поля, убранные в ONE_TIME режиме

- `save_payment_method` (не передаём вообще)
- `payment_method_data` (не нужен)
- `merchant_customer_id` (не нужен для one-time)
- любые recurring-специфичные поля

### Поля, обязательные всегда

- `amount` + `currency`
- `confirmation` (redirect)
- `capture`
- `description`
- `metadata` (с `billing_mode`)

---

## Таблица сравнения режимов

| Параметр | ONE_TIME (false) | RECURRING (true) |
|----------|------------------|------------------|
| `save_payment_method` | не передаётся | `true` |
| `billing_mode` (metadata) | `"ONE_TIME"` | `"RECURRING"` |
| Автопродление | недоступно | доступно после привязки карты |
| 403 Forbidden | не должно быть | может быть, если ЮKassa не настроена |

---

## Частые вопросы

### Q: Что делать, если ошибка 403 осталась даже в ONE_TIME режиме?

**A:** Проверьте:
1. Креды ЮKassa (`YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`)
2. Доступ к API в личном кабинете ЮKassa
3. Лимиты аккаунта (тестовый/боевой режим)

### Q: Как узнать, в каком режиме был создан конкретный платёж?

**A:** Посмотреть в админке Django (`Payment.metadata["billing_mode"]`) или в логах ЮKassa webhook.

### Q: Нужно ли миграция БД?

**A:** Нет. `metadata` — это JSONField, структура не меняется.

### Q: Можно ли включить recurring только для части пользователей?

**A:** Сейчас флаг глобальный. Если нужна гибкость — добавь user flag или feature toggle (не реализовано).

### Q: Что происходит с существующими подписками при переключении режима?

**A:** Ничего. Режим влияет только на **новые** платежи. Старые подписки с привязанными картами продолжат работать.

---

## Мониторинг

### Логи бэкенда

Ищите строку:
```
Built YooKassa payload: mode=ONE_TIME, save_payment_method=False, amount=990.00
```

или

```
Built YooKassa payload: mode=RECURRING, save_payment_method=True, amount=990.00
```

### Webhook логи

В админке Django → `WebhookLog`:
- Проверьте `raw_payload["object"]["metadata"]["billing_mode"]`

### Sentry / Grafana

Ищите:
- `YOOKASSA_FORBIDDEN` — признак, что recurring не включён
- `Create payment error` — общие ошибки создания платежа

---

## Безопасность

1. **Флаг в env, не в коде** — чтобы не делать redeploy при изменении
2. **Прозрачность** — `billing_mode` в metadata для аудита
3. **Понятные ошибки** — 403 с кодом `YOOKASSA_FORBIDDEN`, не 502
4. **Нет магии** — одна функция, одна точка изменения

---

## История изменений

| Дата | Автор | Изменение |
|------|-------|-----------|
| 2025-12-17 | Claude Code | Добавлен переключатель recurring/one-time + документация |

---

## Ссылки

- [YooKassa API docs](https://yookassa.ru/developers/api)
- [Recurring payments guide](https://yookassa.ru/developers/payment-acceptance/scenario-extensions/recurring-payments)
- [payment-flow.md](./payment-flow.md) — общий поток оплаты
- [webhooks.md](./webhooks.md) — обработка webhook
