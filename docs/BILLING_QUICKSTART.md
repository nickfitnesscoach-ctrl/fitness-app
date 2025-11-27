# Billing Settings — Quick Start Guide

Быстрая инструкция для запуска новых эндпоинтов настроек подписки.

---

## Шаг 1: Применить миграции

```bash
cd backend
python manage.py migrate billing
```

**Ожидаемый вывод:**
```
Running migrations:
  Applying billing.0004_add_card_fields_to_subscription... OK
```

---

## Шаг 2: Проверить конфигурацию

```bash
python manage.py check
```

**Должно быть:**
```
System check identified no issues (0 silenced).
```

---

## Шаг 3: Запустить тесты

```bash
python manage.py test apps.billing.tests.SubscriptionDetailsTestCase
python manage.py test apps.billing.tests.AutoRenewToggleTestCase
python manage.py test apps.billing.tests.PaymentMethodDetailsTestCase
python manage.py test apps.billing.tests.PaymentsHistoryTestCase
```

**Все тесты должны пройти (зеленые).**

---

## Шаг 4: Создать тарифные планы (если еще нет)

### Через Django Admin:

1. Запустить сервер: `python manage.py runserver`
2. Открыть: `http://localhost:8000/admin/`
3. Перейти в **Billing → Subscription Plans**
4. Создать планы:

#### FREE план:
- Name: `FREE`
- Display name: `Бесплатный`
- Price: `0.00`
- Duration days: `0`
- Daily photo limit: `3`
- Is active: ✓

#### MONTHLY план:
- Name: `MONTHLY`
- Display name: `Pro Месячный`
- Price: `299.00`
- Duration days: `30`
- Daily photo limit: `null` (безлимит)
- Is active: ✓

---

## Шаг 5: Настроить YooKassa credentials

### В `.env` файле:

```bash
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=test_your_secret_key  # или live_...
```

---

## Шаг 6: Протестировать API

### Простой тест через curl:

```bash
# Получить информацию о подписке
curl -X GET http://localhost:8000/api/v1/billing/subscription/ \
  -H "X-Telegram-Init-Data: <your_init_data>"

# Включить автопродление
curl -X POST http://localhost:8000/api/v1/billing/subscription/autorenew/ \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Init-Data: <your_init_data>" \
  -d '{"enabled": true}'

# История платежей
curl -X GET "http://localhost:8000/api/v1/billing/payments/?limit=5" \
  -H "X-Telegram-Init-Data: <your_init_data>"
```

---

## Доступные эндпоинты

### Settings Screen API:

| Method | Endpoint | Описание |
|--------|----------|----------|
| GET | `/api/v1/billing/subscription/` | Полная информация о подписке |
| POST | `/api/v1/billing/subscription/autorenew/` | Включить/выключить автопродление |
| GET | `/api/v1/billing/payment-method/` | Информация о привязанной карте |
| GET | `/api/v1/billing/payments/` | История платежей |

---

## Frontend Integration

### TypeScript интерфейсы:

```typescript
interface SubscriptionDetails {
  plan: 'free' | 'pro';
  plan_display: string;
  expires_at: string | null;
  is_active: boolean;
  autorenew_available: boolean;
  autorenew_enabled: boolean;
  payment_method: {
    is_attached: boolean;
    card_mask: string | null;
    card_brand: string | null;
  };
}

interface PaymentHistoryItem {
  id: string;
  amount: number;
  currency: string;
  status: 'pending' | 'succeeded' | 'canceled' | 'failed' | 'refunded';
  paid_at: string | null;
  description: string;
}
```

### Пример использования:

```typescript
// Загрузка данных подписки
async function loadSubscription() {
  const response = await fetch('/api/v1/billing/subscription/', {
    headers: {
      'X-Telegram-Init-Data': window.Telegram.WebApp.initData
    }
  });

  const data: SubscriptionDetails = await response.json();

  // Отобразить в UI
  console.log('Plan:', data.plan);
  console.log('Expires:', data.expires_at);
  console.log('Auto-renew:', data.autorenew_enabled);
  console.log('Card:', data.payment_method.card_mask);
}

// Переключение автопродления
async function toggleAutoRenew(enabled: boolean) {
  const response = await fetch('/api/v1/billing/subscription/autorenew/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Telegram-Init-Data': window.Telegram.WebApp.initData
    },
    body: JSON.stringify({ enabled })
  });

  if (!response.ok) {
    const error = await response.json();
    console.error('Error:', error.error.message);
    return;
  }

  const updated: SubscriptionDetails = await response.json();
  console.log('Updated:', updated.autorenew_enabled);
}

// История платежей
async function loadPayments() {
  const response = await fetch('/api/v1/billing/payments/?limit=10', {
    headers: {
      'X-Telegram-Init-Data': window.Telegram.WebApp.initData
    }
  });

  const { results }: { results: PaymentHistoryItem[] } = await response.json();
  console.log('Payments:', results);
}
```

---

## Troubleshooting

### 401 Unauthorized
**Причина:** Нет заголовков аутентификации
**Решение:** Добавьте `X-Telegram-Init-Data` или `Authorization: Bearer <token>`

### 400 payment_method_required
**Причина:** Попытка включить автопродление без привязанной карты
**Решение:** Сначала оплатить подписку с `save_payment_method=true`

### card_mask и card_brand = null
**Причина:** Webhook не получил данные карты от YooKassa
**Решение:** Проверьте логи webhook, убедитесь что `save_payment_method=True` при создании платежа

---

## Полезные ссылки

- **API Documentation:** [docs/billing-settings-api.md](billing-settings-api.md)
- **Manual Testing:** [docs/billing_manual_test.md](billing_manual_test.md)
- **Implementation Summary:** [docs/BILLING_IMPLEMENTATION_SUMMARY.md](BILLING_IMPLEMENTATION_SUMMARY.md)

---

## Next Steps

1. ✅ Миграции применены
2. ✅ Тесты зеленые
3. ✅ Тарифные планы созданы
4. ⏳ Интеграция фронтенда
5. ⏳ Ручное тестирование по чек-листу
6. ⏳ Деплой на прод

**Готово к интеграции!** 🚀
