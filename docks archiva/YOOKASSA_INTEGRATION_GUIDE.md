# YooKassa Интеграция - Руководство по настройке и тестированию

## Обзор изменений

Реализована интеграция YooKassa для покупки подписки Pro (план MONTHLY на 30 дней) с использованием:
- ✅ Собственный клиент без SDK (через requests)
- ✅ Тестовый и боевой режимы (YOOKASSA_MODE=test/prod)
- ✅ Новый endpoint `/api/v1/billing/create-plus-payment/`
- ✅ Новый endpoint `/api/v1/billing/me/` для проверки статуса
- ✅ Обновленный webhook обработчик
- ✅ Полное покрытие тестами

## 1. Настройка переменных окружения

Добавьте в ваш файл `.env`:

```bash
# YooKassa Payment Configuration
YOOKASSA_MODE=test

# Test credentials (ваш ТЕСТОВЫЙ магазин)
YOOKASSA_SHOP_ID_TEST=1201077
YOOKASSA_API_KEY_TEST=test_ВАШ_КЛЮЧ_ОТ_YOOKASSA

# Production credentials (когда будете готовы к продакшену)
YOOKASSA_SHOP_ID_PROD=
YOOKASSA_API_KEY_PROD=

# Return URL after payment
YOOKASSA_RETURN_URL=https://eatfit24.ru/payments/return/

# Webhook secret (опционально, для дополнительной безопасности)
YOOKASSA_WEBHOOK_SECRET=
```

## 2. Миграции базы данных

Модели уже существуют, но на всякий случай проверьте миграции:

```bash
cd backend
python manage.py makemigrations billing
python manage.py migrate billing
```

## 3. Создание тарифных планов в Django Admin

Убедитесь, что в БД есть планы. Войдите в Django Admin и создайте:

### FREE план
- Name: `FREE`
- Display Name: `Бесплатный`
- Price: `0.00`
- Duration Days: `0`
- Is Active: ✅

### MONTHLY план (Pro)
- Name: `MONTHLY`
- Display Name: `Pro Месячный`
- Price: `199.00` (или ваша цена)
- Duration Days: `30`
- Is Active: ✅

### YEARLY план (Pro Годовой) - опционально
- Name: `YEARLY`
- Display Name: `Pro Годовой`
- Price: `1990.00` (или ваша цена)
- Duration Days: `365`
- Is Active: ✅

## 4. Тестирование локально

### 4.1. Создание платежа через API

```bash
# Получите JWT токен вашего пользователя
curl -X POST http://localhost:8000/api/v1/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "your_user", "password": "your_password"}'

# Создайте платеж
curl -X POST http://localhost:8000/api/v1/billing/create-plus-payment/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{}'

# Ответ:
{
  "payment_id": "uuid",
  "yookassa_payment_id": "...",
  "confirmation_url": "https://yoomoney.ru/checkout/payments/v2/contract?orderId=..."
}
```

### 4.2. Проверка статуса подписки

```bash
curl -X GET http://localhost:8000/api/v1/billing/me/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Ответ:
{
  "plan_code": "FREE",
  "plan_name": "Бесплатный",
  "expires_at": null,
  "is_active": true
}
```

### 4.3. Тестирование webhook локально

```bash
# Отправьте тестовый webhook
curl -X POST http://localhost:8000/api/v1/billing/webhooks/yookassa \
  -H "Content-Type: application/json" \
  -d '{
    "type": "notification",
    "event": "payment.succeeded",
    "object": {
      "id": "test-payment-id",
      "status": "succeeded",
      "amount": {
        "value": "199.00",
        "currency": "RUB"
      },
      "payment_method": {
        "type": "bank_card",
        "id": "test-method-id"
      }
    }
  }'
```

## 5. Настройка webhook в личном кабинете YooKassa

1. Войдите в [личный кабинет YooKassa](https://yookassa.ru/my)
2. Перейдите в раздел "Настройки" → "Уведомления"
3. Добавьте URL webhook:
   ```
   https://eatfit24.ru/api/v1/billing/webhooks/yookassa
   ```
4. Выберите события:
   - ✅ `payment.waiting_for_capture`
   - ✅ `payment.succeeded`
   - ✅ `payment.canceled`
   - ✅ `refund.succeeded`

## 6. Запуск тестов

```bash
cd backend

# Запустить все тесты billing
python manage.py test apps.billing

# Запустить конкретный тест
python manage.py test apps.billing.tests.CreateMonthlyPaymentTestCase

# Запустить тесты с подробным выводом
python manage.py test apps.billing --verbosity=2
```

## 7. Структура новых файлов

```
backend/apps/billing/
├── yookassa_client.py          # NEW: Клиент для YooKassa API без SDK
├── services.py                 # UPDATED: Добавлены сервисы для платежей
├── views.py                    # UPDATED: Новые endpoints
├── webhooks.py                 # UPDATED: Обновлен обработчик webhook
├── urls.py                     # UPDATED: Новые маршруты
├── tests.py                    # UPDATED: Тесты для новой функциональности
└── models.py                   # EXISTING: Без изменений
```

## 8. API Endpoints

### POST /api/v1/billing/create-plus-payment/
Создание платежа для Pro подписки (месячный план).

**Request:**
```json
{
  "return_url": "https://yoursite.com/success" // опционально
}
```

**Response (201):**
```json
{
  "payment_id": "uuid",
  "yookassa_payment_id": "2d8ee25e-000f-5000-9000-1b7b0c8d5c76",
  "confirmation_url": "https://yoomoney.ru/checkout/payments/..."
}
```

**Errors:**
- `400 BAD_REQUEST` - План не найден или ошибка валидации
- `502 BAD_GATEWAY` - Ошибка создания платежа в YooKassa

---

### GET /api/v1/billing/me/
Получение текущего статуса подписки.

**Response (200):**
```json
{
  "plan_code": "MONTHLY",
  "plan_name": "Pro Месячный",
  "expires_at": "2024-12-31T23:59:59Z",
  "is_active": true
}
```

---

### POST /api/v1/billing/webhooks/yookassa
Webhook для обработки уведомлений от YooKassa.

**Security:**
- IP whitelist (только адреса YooKassa)
- Rate limiting: 100 requests/hour
- Идемпотентность (повторные вызовы безопасны)

## 9. Логика работы платежей

1. **Пользователь инициирует покупку** → `POST /api/v1/billing/create-plus-payment/`
2. **Backend создает запись Payment** в статусе `PENDING`
3. **Backend обращается к YooKassa API** → получает `confirmation_url`
4. **Фронтенд/бот открывает** `confirmation_url` для пользователя
5. **Пользователь оплачивает** через YooKassa
6. **YooKassa отправляет webhook** → `payment.succeeded`
7. **Backend обрабатывает webhook**:
   - Обновляет Payment → `SUCCEEDED`
   - Активирует/продлевает подписку на 30 дней
   - Обновляет план пользователя на `MONTHLY`

## 10. Безопасность

✅ **IP Whitelist** - Webhook принимает запросы только с IP YooKassa
✅ **Rate Limiting** - 100 запросов в час на webhook
✅ **Idempotence** - Повторная обработка платежа безопасна
✅ **Transaction Locks** - Используется `select_for_update()`
✅ **Audit Logging** - Все платежи логируются через SecurityAuditLogger

## 11. Переключение в Production

Когда будете готовы к продакшену:

1. Получите **боевые credentials** от YooKassa
2. Обновите `.env`:
   ```bash
   YOOKASSA_MODE=prod
   YOOKASSA_SHOP_ID_PROD=ваш_боевой_shop_id
   YOOKASSA_API_KEY_PROD=live_ваш_боевой_ключ
   ```
3. Обновите webhook URL в YooKassa на боевой:
   ```
   https://eatfit24.ru/api/v1/billing/webhooks/yookassa
   ```
4. Протестируйте на небольшой сумме

## 12. Troubleshooting

### Платеж не создается
- Проверьте credentials в `.env`
- Проверьте логи: `tail -f backend/logs/django.log`
- Убедитесь, что план `MONTHLY` активен в БД

### Webhook не приходит
- Проверьте URL в настройках YooKassa
- Проверьте, что сервер доступен извне
- Проверьте IP whitelist (отключите для localhost в DEBUG mode)

### Подписка не активируется
- Проверьте, что webhook обработан успешно (логи)
- Проверьте `yookassa_payment_id` в БД
- Убедитесь, что у пользователя есть Subscription

## 13. Полезные команды

```bash
# Просмотр логов
tail -f backend/logs/django.log

# Проверка платежей в БД
python manage.py shell
>>> from apps.billing.models import Payment
>>> Payment.objects.all()

# Очистка тестовых платежей
>>> Payment.objects.filter(status='PENDING').delete()

# Проверка подписок
>>> from apps.billing.models import Subscription
>>> Subscription.objects.filter(plan__name='MONTHLY')
```

## 14. Контакты и поддержка

- **YooKassa документация**: https://yookassa.ru/developers/api
- **YooKassa поддержка**: https://yookassa.ru/contacts
- **Личный кабинет**: https://yookassa.ru/my

---

**Готово!** Интеграция YooKassa полностью настроена и готова к тестированию. 🚀
