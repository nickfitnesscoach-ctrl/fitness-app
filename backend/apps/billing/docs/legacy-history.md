# История Legacy

Документ описывает удалённый legacy-код и причины его удаления.

## Удалённые компоненты

### yookassa_client.py

**Что это было:**
- Низкоуровневый HTTP-клиент для YooKassa через `requests`
- Класс `YooKassaClient` с методами `create_payment()`, `get_payment_info()`

**Почему удалён:**
- Дублировал функциональность `YooKassaService` (SDK)
- Использовался только в тестах
- Создавал путаницу: два клиента для одного API

**Миграция:**
- Все вызовы перенесены на `YooKassaService`
- Тесты обновлены для мочки `YooKassaService`

**Дата удаления:** 2024-12

---

### Legacy endpoints

**Удалённые endpoints:**

| Endpoint | Причина |
|----------|---------|
| `GET /billing/plan` | Заменён на `/billing/me/` |
| `POST /billing/subscribe` | Заменён на `/billing/create-payment/` |
| `POST /billing/create-plus-payment/` | Дублировал `/billing/create-payment/` |
| `POST /billing/auto-renew/toggle` | Заменён на `/billing/subscription/autorenew/` |
| `GET /billing/payments` (без `/`) | Заменён на `/billing/payments/` |

**Миграция:**
- Фронтенд обновлён на новые endpoints
- Старые endpoints имели `@deprecated` декоратор
- После мониторинга (0 вызовов) — удалены

---

### Frontend legacy функции

**Удалённые функции:**

| Функция | Причина |
|---------|---------|
| `cancelSubscription()` | Backend endpoint не существовал |
| `resumeSubscription()` | Backend endpoint не существовал |
| `getSubscriptionPlan()` | Заменена на `getBillingMe()` |

**Удалённые URL constants:**
- `URLS.plan`
- `URLS.cancelSubscription`
- `URLS.resumeSubscription`
- `URLS.paymentMethods`

---

## Принципы удаления legacy

1. **Добавить @deprecated** — пометить устаревшим
2. **Добавить логирование** — считать вызовы
3. **Мониторинг 14-30 дней** — убедиться в 0 вызовов
4. **Удалить** — только после подтверждения

## Что НЕ удалять

| Компонент | Причина |
|-----------|---------|
| `SubscriptionPlan.name` | Legacy поле, но используется для fallback |
| `SubscriptionPlan.max_photos_per_day` | Legacy, но может быть в старых данных |
| сигнал `create_free_subscription` | Критичен для регистрации |

---

## Timeline

| Дата | Действие |
|------|----------|
| 2024-12-17 | Удалён `yookassa_client.py` |
| 2024-12-17 | Удалены legacy endpoints из `urls.py` |
| 2024-12-17 | Удалены legacy views из `views.py` |
| 2024-12-17 | Frontend cleanup: удалены unused функции |
