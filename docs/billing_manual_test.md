# Manual Testing Checklist — Billing & Settings Endpoints

## Подготовка к тестированию

### Требования
- [ ] Backend запущен и доступен
- [ ] База данных мигрирована (`python manage.py migrate`)
- [ ] Созданы тарифные планы (FREE, MONTHLY, YEARLY) через Django Admin
- [ ] Есть тестовый аккаунт YooKassa (test режим)
- [ ] Telegram Mini App запущен или доступны тестовые заголовки для аутентификации

### Тестовые данные

Создайте несколько тестовых пользователей:
1. **User A** — без подписки (Free)
2. **User B** — с PRO без привязанной карты
3. **User C** — с PRO и привязанной картой
4. **User D** — с PRO и включенным автопродлением

---

## Тест 1: GET /api/v1/billing/subscription/

### 1.1 Пользователь без подписки (Free)

**Шаги:**
1. Войти как User A (новый пользователь без подписки)
2. Отправить GET запрос на `/api/v1/billing/subscription/`

**Ожидаемый результат:**
```json
{
  "plan": "free",
  "plan_display": "Free",
  "expires_at": null,
  "is_active": true,
  "autorenew_available": false,
  "autorenew_enabled": false,
  "payment_method": {
    "is_attached": false,
    "card_mask": null,
    "card_brand": null
  }
}
```

**Проверка:**
- [ ] Статус ответа: 200 OK
- [ ] `plan` = "free"
- [ ] `expires_at` = null
- [ ] `autorenew_available` = false
- [ ] `payment_method.is_attached` = false

---

### 1.2 Пользователь с PRO без карты

**Шаги:**
1. Войти как User B (PRO без карты)
2. Отправить GET запрос на `/api/v1/billing/subscription/`

**Ожидаемый результат:**
```json
{
  "plan": "pro",
  "plan_display": "PRO",
  "expires_at": "2025-XX-XX",  // Дата окончания
  "is_active": true,
  "autorenew_available": false,  // Нет карты
  "autorenew_enabled": false,
  "payment_method": {
    "is_attached": false,
    "card_mask": null,
    "card_brand": null
  }
}
```

**Проверка:**
- [ ] Статус ответа: 200 OK
- [ ] `plan` = "pro"
- [ ] `expires_at` содержит дату в формате YYYY-MM-DD
- [ ] `is_active` = true
- [ ] `autorenew_available` = false (нет карты!)
- [ ] `payment_method.is_attached` = false

---

### 1.3 Пользователь с PRO и привязанной картой

**Шаги:**
1. Войти как User C (PRO с картой)
2. Отправить GET запрос на `/api/v1/billing/subscription/`

**Ожидаемый результат:**
```json
{
  "plan": "pro",
  "plan_display": "PRO",
  "expires_at": "2025-XX-XX",
  "is_active": true,
  "autorenew_available": true,  // Есть карта
  "autorenew_enabled": true,    // Может быть включено
  "payment_method": {
    "is_attached": true,
    "card_mask": "•••• 1234",
    "card_brand": "Visa"
  }
}
```

**Проверка:**
- [ ] Статус ответа: 200 OK
- [ ] `plan` = "pro"
- [ ] `autorenew_available` = true
- [ ] `payment_method.is_attached` = true
- [ ] `payment_method.card_mask` не null (например "•••• 1234")
- [ ] `payment_method.card_brand` не null (например "Visa", "MasterCard")

---

### 1.4 Без авторизации

**Шаги:**
1. Отправить GET запрос на `/api/v1/billing/subscription/` БЕЗ заголовков авторизации

**Ожидаемый результат:**
- Статус ответа: 401 Unauthorized

**Проверка:**
- [ ] Статус ответа: 401
- [ ] Есть сообщение об ошибке аутентификации

---

## Тест 2: POST /api/v1/billing/subscription/autorenew/

### 2.1 Включение автопродления без карты (ошибка)

**Шаги:**
1. Войти как User B (PRO без карты)
2. Отправить POST запрос на `/api/v1/billing/subscription/autorenew/`
   ```json
   {
     "enabled": true
   }
   ```

**Ожидаемый результат:**
```json
{
  "error": {
    "code": "payment_method_required",
    "message": "Для автопродления необходима привязанная карта..."
  }
}
```

**Проверка:**
- [ ] Статус ответа: 400 Bad Request
- [ ] `error.code` = "payment_method_required"
- [ ] Есть понятное сообщение об ошибке

---

### 2.2 Включение автопродления с картой (успех)

**Шаги:**
1. Войти как User C (PRO с картой, автопродление выключено)
2. Отправить POST запрос на `/api/v1/billing/subscription/autorenew/`
   ```json
   {
     "enabled": true
   }
   ```

**Ожидаемый результат:**
- Статус ответа: 200 OK
- Возвращается полный объект подписки с `autorenew_enabled` = true

**Проверка:**
- [ ] Статус ответа: 200 OK
- [ ] `autorenew_enabled` = true
- [ ] `autorenew_available` = true
- [ ] Флаг сохранился в БД (проверить через GET запрос или Django Admin)

---

### 2.3 Отключение автопродления

**Шаги:**
1. Войти как User D (PRO с включенным автопродлением)
2. Отправить POST запрос на `/api/v1/billing/subscription/autorenew/`
   ```json
   {
     "enabled": false
   }
   ```

**Ожидаемый результат:**
- Статус ответа: 200 OK
- `autorenew_enabled` = false

**Проверка:**
- [ ] Статус ответа: 200 OK
- [ ] `autorenew_enabled` = false
- [ ] Флаг сохранился в БД
- [ ] После повторного GET запроса статус остается false

---

### 2.4 Включение автопродления на бесплатном плане (ошибка)

**Шаги:**
1. Войти как User A (Free план)
2. Отправить POST запрос на `/api/v1/billing/subscription/autorenew/`
   ```json
   {
     "enabled": true
   }
   ```

**Ожидаемый результат:**
```json
{
  "error": {
    "code": "NOT_AVAILABLE_FOR_FREE",
    "message": "Автопродление недоступно для бесплатного плана"
  }
}
```

**Проверка:**
- [ ] Статус ответа: 400 Bad Request
- [ ] `error.code` = "NOT_AVAILABLE_FOR_FREE"

---

## Тест 3: GET /api/v1/billing/payment-method/

### 3.1 Без привязанной карты

**Шаги:**
1. Войти как User A или User B (нет карты)
2. Отправить GET запрос на `/api/v1/billing/payment-method/`

**Ожидаемый результат:**
```json
{
  "is_attached": false,
  "card_mask": null,
  "card_brand": null
}
```

**Проверка:**
- [ ] Статус ответа: 200 OK
- [ ] `is_attached` = false
- [ ] `card_mask` = null
- [ ] `card_brand` = null

---

### 3.2 С привязанной картой

**Шаги:**
1. Войти как User C (есть карта)
2. Отправить GET запрос на `/api/v1/billing/payment-method/`

**Ожидаемый результат:**
```json
{
  "is_attached": true,
  "card_mask": "•••• 1234",
  "card_brand": "Visa"
}
```

**Проверка:**
- [ ] Статус ответа: 200 OK
- [ ] `is_attached` = true
- [ ] `card_mask` содержит маску (например "•••• 1234")
- [ ] `card_brand` содержит тип карты (например "Visa", "MasterCard")

---

## Тест 4: GET /api/v1/billing/payments/

### 4.1 История платежей (пустая)

**Шаги:**
1. Войти как новый пользователь без платежей
2. Отправить GET запрос на `/api/v1/billing/payments/`

**Ожидаемый результат:**
```json
{
  "results": []
}
```

**Проверка:**
- [ ] Статус ответа: 200 OK
- [ ] `results` = пустой массив

---

### 4.2 История платежей (с данными)

**Подготовка:**
1. Создать несколько платежей для User C через Django Admin или API

**Шаги:**
1. Войти как User C
2. Отправить GET запрос на `/api/v1/billing/payments/`

**Ожидаемый результат:**
```json
{
  "results": [
    {
      "id": "uuid-here",
      "amount": 299.00,
      "currency": "RUB",
      "status": "succeeded",
      "paid_at": "2025-02-10T12:34:56Z",
      "description": "Подписка Pro Месячный"
    }
  ]
}
```

**Проверка:**
- [ ] Статус ответа: 200 OK
- [ ] `results` содержит платежи
- [ ] Платежи отсортированы от новых к старым
- [ ] Каждый платеж содержит все обязательные поля: id, amount, currency, status, paid_at, description
- [ ] `status` в lowercase ("succeeded", "pending", etc.)

---

### 4.3 Ограничение limit

**Шаги:**
1. Войти как пользователь с 15+ платежами
2. Отправить GET запрос на `/api/v1/billing/payments/?limit=5`

**Ожидаемый результат:**
- Возвращается только 5 платежей (самые новые)

**Проверка:**
- [ ] Статус ответа: 200 OK
- [ ] `results.length` = 5
- [ ] Это 5 самых новых платежей

---

### 4.4 Изоляция пользователей

**Шаги:**
1. Создать платежи для User C и User D
2. Войти как User C
3. Отправить GET запрос на `/api/v1/billing/payments/`

**Ожидаемый результат:**
- Возвращаются только платежи User C

**Проверка:**
- [ ] Статус ответа: 200 OK
- [ ] Возвращаются только платежи текущего пользователя
- [ ] Нет платежей других пользователей

---

## Тест 5: Интеграция с платежами (E2E)

### 5.1 Полный цикл: покупка PRO → привязка карты → автопродление

**Шаги:**
1. Войти как новый пользователь (Free)
2. Проверить `/billing/subscription/` — должен быть Free
3. Создать платеж через `/billing/create-payment/` для MONTHLY плана
4. Оплатить через YooKassa (тестовая карта)
5. Webhook `payment.succeeded` должен сработать и:
   - Активировать PRO подписку
   - Сохранить `payment_method_id`, `card_mask`, `card_brand`
   - Включить `auto_renew = True`
6. Проверить `/billing/subscription/` — должны появиться:
   - `plan` = "pro"
   - `autorenew_available` = true
   - `autorenew_enabled` = true
   - `payment_method.is_attached` = true
   - `payment_method.card_mask` и `card_brand` заполнены
7. Проверить `/billing/payments/` — должен появиться успешный платеж
8. Выключить автопродление через `/billing/subscription/autorenew/`
9. Проверить, что флаг обновился

**Проверка:**
- [ ] После успешной оплаты подписка активирована
- [ ] Карта привязана (видна маска и бренд)
- [ ] Автопродление автоматически включено
- [ ] Можно выключить/включить автопродление
- [ ] История платежей содержит успешный платеж

---

## Итоговая проверка

### UI экрана "Настройки"

**Проверка для каждого сценария:**

1. **Free пользователь:**
   - [ ] Отображается "Тариф: Free"
   - [ ] Нет даты окончания
   - [ ] Toggle "Автопродление" отключен и недоступен
   - [ ] Способ оплаты: "Не привязан"

2. **PRO без карты:**
   - [ ] Отображается "Тариф: PRO до [дата]"
   - [ ] Toggle "Автопродление" отключен и недоступен
   - [ ] Сообщение: "Автопродление недоступно — привяжите карту..."
   - [ ] Способ оплаты: "Не привязан"

3. **PRO с картой:**
   - [ ] Отображается "Тариф: PRO до [дата]"
   - [ ] Toggle "Автопродление" доступен и работает
   - [ ] Способ оплаты: "Visa •••• 1234" (или другая карта)
   - [ ] История оплат отображается корректно

---

## Регрессионное тестирование

### Проверка, что старые эндпоинты не сломались:

- [ ] `GET /billing/plan` — работает
- [ ] `GET /billing/me/` — работает
- [ ] `POST /billing/create-payment/` — работает
- [ ] `POST /billing/auto-renew/toggle` — работает (deprecated)
- [ ] `GET /billing/payments` — работает (deprecated, без trailing slash)

---

## Проверка безопасности

- [ ] Нельзя получить данные чужого пользователя
- [ ] Нельзя изменить автопродление чужого пользователя
- [ ] `payment_method_id` не возвращается в API (только маска и бренд)
- [ ] Все эндпоинты требуют аутентификации
- [ ] 401 при отсутствии авторизации

---

## Проверка производительности

- [ ] GET `/subscription/` отвечает < 500ms
- [ ] GET `/payments/?limit=10` отвечает < 500ms
- [ ] POST `/autorenew/` отвечает < 500ms
- [ ] Нет N+1 запросов к БД (проверить через Django Debug Toolbar)

---

## Заметки

**Тестовые карты YooKassa (test режим):**
- Успешная оплата: `5555 5555 5555 4444`, CVC: любой, срок: будущий
- Отклоненная оплата: `5555 5555 5555 5599`

**Useful commands:**
```bash
# Запуск тестов
python manage.py test apps.billing

# Создание миграций
python manage.py makemigrations billing

# Применение миграций
python manage.py migrate

# Запуск сервера
python manage.py runserver
```
