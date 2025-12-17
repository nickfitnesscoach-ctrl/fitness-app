# Известные ограничения биллинга EatFit24

Этот документ описывает текущие ограничения и временные решения в биллинг-модуле.

---

## 1. YooKassa Recurring Payments

### Статус
⚠️ **Временно отключено** (с 2025-12-17)

### Проблема
YooKassa возвращает **403 Forbidden** при попытке создания платежа с `save_payment_method=true`.

**Причина:** Рекуррентные платежи не активированы на аккаунте YooKassa.

### Временное решение
Реализован **переключатель режимов** (ONE_TIME / RECURRING):

```bash
# В /opt/EatFit24/.env
BILLING_RECURRING_ENABLED=false  # ONE_TIME mode (текущий)
```

**ONE_TIME режим:**
- Единоразовые платежи
- Карта НЕ сохраняется
- Автопродление НЕДОСТУПНО
- Нет ошибок 403

**Документация:** См. [RECURRING_SWITCH.md](./RECURRING_SWITCH.md)

### Когда будет исправлено
Когда YooKassa активирует recurring на аккаунте:
1. Изменить `BILLING_RECURRING_ENABLED=true` в `.env`
2. Перезапустить: `docker compose restart backend celery-worker`
3. Протестировать создание платежа

**Ответственный:** Владелец аккаунта YooKassa (активация в личном кабинете)

---

## 2. Автопродление подписок

### Статус
⚠️ **Недоступно** (пока `BILLING_RECURRING_ENABLED=false`)

### Проблема
Для автопродления нужна привязанная карта (payment_method_id), что требует recurring режима.

### Временное решение
Пользователи должны **вручную продлевать** подписку каждый месяц.

**В UI:**
- Скрыта кнопка "Включить автопродление" (если `card_bound=false`)
- Показывается сообщение "Автопродление недоступно"

### Когда будет исправлено
После включения `BILLING_RECURRING_ENABLED=true` (см. пункт 1).

---

## 3. Привязка карты (bind card)

### Статус
⚠️ **Недоступно** (пока `BILLING_RECURRING_ENABLED=false`)

### Проблема
Endpoint `/api/v1/billing/bind-card/start/` создаёт платёж с `save_payment_method=true`, что требует recurring.

### Временное решение
Endpoint возвращает **403 Forbidden** с понятным сообщением:
```json
{
  "error": {
    "code": "CARD_BINDING_NOT_AVAILABLE",
    "message": "Привязка карты временно недоступна."
  }
}
```

**В UI:**
- Скрыта кнопка "Привязать карту"

### Когда будет исправлено
После включения `BILLING_RECURRING_ENABLED=true`.

---

## 4. Тестовый live-платёж (1₽)

### Статус
✅ **Работает** (если `YOOKASSA_MODE=prod` и пользователь — админ)

### Ограничение
Доступен ТОЛЬКО админам (проверка через `TELEGRAM_ADMINS`).

### Почему так
Это инструмент для проверки боевого магазина YooKassa без создания реальных подписок.

**Безопасность:**
- Требует аутентификации
- Требует `telegram_id in TELEGRAM_ADMINS`
- Требует `YOOKASSA_MODE=prod`

**Endpoint:** `POST /api/v1/billing/create-test-live-payment/`

---

## 5. FREE план: end_date через 10 лет

### Статус
✅ **By design** (не баг)

### Почему так
FREE подписка логически "не истекает", но поле `end_date` (NOT NULL) требует дату.

**Решение:**
```python
end_date = timezone.now() + timedelta(days=365 * 10)
```

**В коде:**
- `Subscription.is_expired()` для FREE всегда возвращает `False`
- `days_remaining` для FREE возвращает `None`

**Настройка:**
```python
# В settings.py (опционально)
FREE_SUBSCRIPTION_END_DATE = timezone.make_aware(datetime(2099, 12, 31))
```

---

## 6. Поддержка только ЮKassa

### Статус
✅ **By design**

### Ограничение
Приложение работает ТОЛЬКО с YooKassa (Яндекс.Касса).

**Не поддерживается:**
- Stripe
- PayPal
- Банковские переводы
- Cryptocurrency

### Если нужен другой провайдер
1. Добавить модель `Provider` (таблица)
2. Расширить `Payment.provider` (choices)
3. Создать адаптер (аналог `YooKassaService`)
4. Обновить `create_subscription_payment()` (выбор провайдера)

**Сложность:** ~2-3 дня разработки + тестирование

---

## 7. Валюта: только RUB

### Статус
✅ **By design**

### Ограничение
Приложение работает только с российскими рублями (RUB).

**Почему:**
- Целевая аудитория: Россия
- YooKassa по умолчанию работает с RUB
- Упрощает биллинг (нет конвертации)

### Если нужна мультивалютность
1. Добавить `currency` в `SubscriptionPlan`
2. Поддержать конвертацию (API rates)
3. Обновить UI (показ цены в разных валютах)

**Сложность:** ~1 неделя разработки

---

## 8. Webhook retry: нет автоматических повторов

### Статус
⚠️ **Планируется** (не реализовано)

### Проблема
Если webhook от YooKassa не обработался (ошибка БД, таймаут и т.д.), повтора НЕ будет.

**Текущее поведение:**
- Webhook логируется в `WebhookLog`
- Статус `FAILED` сохраняется
- Но НЕ перезапускается автоматически

### Временное решение
**Ручной retry:**
1. Django Admin → WebhookLog
2. Найти FAILED webhook
3. Скопировать `raw_payload`
4. Отправить POST на `/api/v1/billing/webhooks/yookassa/`

### Планы
Добавить Celery task для автоматического retry:
- Через 5 минут (1 попытка)
- Через 30 минут (2 попытка)
- Через 2 часа (3 попытка)

**Статус:** В бэклоге

---

## 9. Rate limiting: 20 платежей/час

### Статус
✅ **By design** (безопасность)

### Ограничение
Пользователь может создать максимум **20 платежей в час**.

**Зачем:**
- Защита от злоупотреблений
- Защита от случайных duplicate кликов
- Защита от DoS

**Throttle:**
```python
@throttle_classes([PaymentCreationThrottle])  # 20 req/hour
```

**Если пользователь превысил лимит:**
```json
{
  "detail": "Request was throttled. Expected available in 3600 seconds."
}
```

**Настройка:**
```python
# apps/billing/throttles.py
class PaymentCreationThrottle(UserRateThrottle):
    rate = '20/hour'  # Можно изменить
```

---

## 10. Legacy поля: name и max_photos_per_day

### Статус
✅ **Deprecated** (но не удалены)

### Почему остались
Обратная совместимость со старыми частями кода.

**Deprecated:**
- `SubscriptionPlan.name` → используйте `code`
- `SubscriptionPlan.max_photos_per_day` → используйте `daily_photo_limit`

**План:**
1. Миграция всех ссылок на новые поля
2. Добавить `DeprecationWarning` в модель
3. Удалить в следующей мажорной версии

**Статус:** В бэклоге

---

## Чеклист готовности к продакшену

### Биллинг

- [x] FREE план создан (`code=FREE`, `price=0`)
- [x] PRO_MONTHLY план создан (`code=PRO_MONTHLY`)
- [x] PRO_YEARLY план создан (`code=PRO_YEARLY`)
- [x] `BILLING_RECURRING_ENABLED=false` в prod `.env`
- [x] YooKassa креды настроены (`YOOKASSA_SHOP_ID`, `YOOKASSA_SECRET_KEY`)
- [x] `YOOKASSA_MODE=prod` в prod `.env`
- [x] `YOOKASSA_RETURN_URL` настроен
- [x] `ALLOWED_RETURN_URL_DOMAINS` настроен (защита от open redirect)
- [ ] Recurring платежи активированы в YooKassa (когда будет доступно)
- [x] Webhook URL зарегистрирован в YooKassa: `https://eatfit24.ru/api/v1/billing/webhooks/yookassa/`

### Мониторинг

- [ ] Sentry настроен для ошибок биллинга
- [ ] Grafana dashboard для метрик платежей
- [ ] Алерты на FAILED платежи (>10 в час)
- [ ] Алерты на FAILED webhooks

### Тестирование

- [x] Unit тесты для `build_yookassa_payment_payload()`
- [ ] Integration тесты для webhook обработки
- [ ] E2E тест полного флоу оплаты (Mini App → YooKassa → webhook → подписка)

---

## История изменений

| Дата | Изменение |
|------|-----------|
| 2025-12-17 | Создан документ. Добавлен переключатель recurring/one-time. |

---

## Контакты

**Вопросы:** См. [README.md](./README.md)
**Recurring switch:** См. [RECURRING_SWITCH.md](./RECURRING_SWITCH.md)
