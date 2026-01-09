# API CONTRACT — Billing Feature Module

> Документация API-контрактов для фронтенда биллинга.

---

## Эндпоинты

### GET /billing/me/

Получение статуса подписки и лимитов.

**Response:**
```typescript
interface BillingMe {
    plan_code: 'FREE' | 'PRO_MONTHLY' | 'PRO_YEARLY';
    plan_name: string;
    expires_at: string | null;  // ISO 8601
    is_active: boolean;
    daily_photo_limit: number | null;  // null = безлимит
    used_today: number;
    remaining_today: number | null;    // null = безлимит
    test_live_payment_available?: boolean;  // Только для админов
}
```

---

### GET /billing/plans/

Получение списка доступных тарифов.

**Response:**
```typescript
interface SubscriptionPlan {
    code: string;  // 'FREE' | 'PRO_MONTHLY' | 'PRO_YEARLY'
    display_name: string;
    price: number;
    duration_days: number;
    daily_photo_limit: number | null;
    history_days: number;  // -1 = безлимит
    ai_recognition: boolean;
    advanced_stats: boolean;
    priority_support: boolean;
    features?: string[];
    is_popular?: boolean;
    old_price?: number;
}
```

---

### GET /billing/subscription/

Детальная информация о подписке.

**Response:**
```typescript
interface SubscriptionDetails {
    plan: 'free' | 'pro';
    plan_display: string;
    expires_at: string | null;
    is_active: boolean;
    autorenew_available: boolean;
    autorenew_enabled: boolean;
    card_bound: boolean;
    payment_method: {
        is_attached: boolean;
        card_mask: string | null;  // "•••• 1234"
        card_brand: string | null; // "Visa", "MasterCard"
    };
}
```

---

### POST /billing/subscription/autorenew/

Включение/выключение автопродления.

**Request:**
```typescript
interface AutoRenewRequest {
    enabled: boolean;
}
```

**Response:** `SubscriptionDetails`

**Ошибки:**
- `NO_PAYMENT_METHOD` — карта не привязана
- `NO_SUBSCRIPTION` — нет активной подписки

---

### POST /billing/create-payment/

Создание платежа для покупки подписки.

**Request:**
```typescript
interface CreatePaymentRequest {
    plan_code: string;
    return_url?: string;
    save_payment_method?: boolean;
}
```

**Response:**
```typescript
interface CreatePaymentResponse {
    payment_id: string;
    yookassa_payment_id: string;
    confirmation_url: string;
}
```

**Ошибки:**
- `INVALID_PLAN` — недопустимый plan_code
- `ACTIVE_SUBSCRIPTION` — уже есть активная подписка
- `PAYMENT_ERROR` — ошибка YooKassa

---

### POST /billing/bind-card/start/

Начало привязки карты (платёж 1₽).

**Request:** `{}`

**Response:**
```typescript
{
    payment_id: string;
    confirmation_url: string;
}
```

---

### GET /billing/payment-method/

Информация о привязанной карте.

**Response:**
```typescript
interface PaymentMethod {
    is_attached: boolean;
    card_mask: string | null;
    card_brand: string | null;
}
```

---

### GET /billing/payments/

История платежей.

**Query params:**
- `limit` — количество записей (default: 10)

**Response:**
```typescript
interface PaymentHistory {
    results: PaymentHistoryItem[];
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

---

## Коды ошибок

| Код | Описание |
|-----|----------|
| `DAILY_LIMIT_REACHED` | Исчерпан дневной лимит фото |
| `NO_SUBSCRIPTION` | Подписка не найдена |
| `INVALID_PLAN` | Недопустимый тариф |
| `PAYMENT_ERROR` | Ошибка создания платежа |
| `NO_PAYMENT_METHOD` | Карта не привязана |
| `NOT_AVAILABLE_FOR_FREE` | Функция недоступна для FREE |
| `ACTIVE_SUBSCRIPTION` | Уже есть активная подписка |
