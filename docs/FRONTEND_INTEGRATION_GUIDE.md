# Frontend Integration Guide — Settings Screen API

## Текущая ситуация

✅ **Backend готов:**
- Миграции применены на сервере
- API эндпоинты работают: `/api/v1/billing/subscription/`, `/subscription/autorenew/`, `/payment-method/`, `/payments/`
- Все тесты проходят

⚠️ **Frontend частично готов:**
- UI экрана "Настройки" уже реализован в `SettingsPage.tsx`
- `BillingContext` существует, но использует старый эндпоинт `/billing/me/`
- Нужно обновить API методы для использования новых эндпоинтов

---

## Что нужно сделать

### 1. Обновить TypeScript типы

Файл: `frontend/src/types/billing.ts`

Добавьте новые интерфейсы:

```typescript
/**
 * Новый формат ответа GET /api/v1/billing/subscription/
 */
export interface SubscriptionDetails {
  plan: 'free' | 'pro';
  plan_display: string;
  expires_at: string | null;  // YYYY-MM-DD или null
  is_active: boolean;
  autorenew_available: boolean;
  autorenew_enabled: boolean;
  payment_method: {
    is_attached: boolean;
    card_mask: string | null;    // "•••• 1234"
    card_brand: string | null;   // "Visa", "MasterCard"
  };
}

/**
 * Способ оплаты GET /api/v1/billing/payment-method/
 */
export interface PaymentMethod {
  is_attached: boolean;
  card_mask: string | null;
  card_brand: string | null;
}

/**
 * Элемент истории платежей
 */
export interface PaymentHistoryItem {
  id: string;
  amount: number;
  currency: string;
  status: 'pending' | 'succeeded' | 'canceled' | 'failed' | 'refunded';
  paid_at: string | null;  // ISO 8601
  description: string;
}

/**
 * История платежей GET /api/v1/billing/payments/
 */
export interface PaymentHistory {
  results: PaymentHistoryItem[];
}

/**
 * Запрос для toggle auto-renew
 */
export interface AutoRenewRequest {
  enabled: boolean;
}
```

---

### 2. Обновить API сервис

Файл: `frontend/src/services/api.ts`

#### 2.1 Добавьте новые URL константы:

```typescript
const URLS = {
  // ... существующие URL

  // NEW: Settings screen endpoints
  subscriptionDetails: `${API_BASE}/billing/subscription/`,
  subscriptionAutoRenew: `${API_BASE}/billing/subscription/autorenew/`,
  paymentMethodDetails: `${API_BASE}/billing/payment-method/`,
  paymentsHistory: `${API_BASE}/billing/payments/`,
};
```

#### 2.2 Добавьте новые API методы:

```typescript
/**
 * GET /api/v1/billing/subscription/
 * Получение полной информации о подписке для настроек
 */
async getSubscriptionDetails(): Promise<SubscriptionDetails> {
  log('Fetching subscription details');
  try {
    const response = await fetchWithRetry(URLS.subscriptionDetails, {
      headers: getHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch subscription details: ${response.status}`);
    }

    const data = await response.json();
    log('Subscription details fetched successfully');
    return data;
  } catch (error) {
    log(`Failed to fetch subscription details: ${error}`);
    throw error;
  }
},

/**
 * POST /api/v1/billing/subscription/autorenew/
 * Включение/отключение автопродления
 */
async setAutoRenew(enabled: boolean): Promise<SubscriptionDetails> {
  log(`Setting auto-renew: ${enabled}`);
  try {
    const response = await fetchWithRetry(URLS.subscriptionAutoRenew, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ enabled }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error?.message || 'Failed to toggle auto-renew');
    }

    const data = await response.json();
    log('Auto-renew toggled successfully');
    return data;
  } catch (error) {
    log(`Failed to toggle auto-renew: ${error}`);
    throw error;
  }
},

/**
 * GET /api/v1/billing/payment-method/
 * Получение информации о привязанном способе оплаты
 */
async getPaymentMethod(): Promise<PaymentMethod> {
  log('Fetching payment method');
  try {
    const response = await fetchWithRetry(URLS.paymentMethodDetails, {
      headers: getHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch payment method: ${response.status}`);
    }

    const data = await response.json();
    log('Payment method fetched successfully');
    return data;
  } catch (error) {
    log(`Failed to fetch payment method: ${error}`);
    throw error;
  }
},

/**
 * GET /api/v1/billing/payments/?limit=10
 * Получение истории платежей
 */
async getPaymentsHistory(limit = 10): Promise<PaymentHistory> {
  log(`Fetching payments history (limit: ${limit})`);
  try {
    const response = await fetchWithRetry(`${URLS.paymentsHistory}?limit=${limit}`, {
      headers: getHeaders(),
    });

    if (!response.ok) {
      throw new Error(`Failed to fetch payments history: ${response.status}`);
    }

    const data = await response.json();
    log(`Payments history fetched: ${data.results.length} items`);
    return data;
  } catch (error) {
    log(`Failed to fetch payments history: ${error}`);
    throw error;
  }
},
```

---

### 3. Обновить BillingContext

Файл: `frontend/src/contexts/BillingContext.tsx`

#### 3.1 Обновите интерфейс контекста:

```typescript
interface BillingContextType {
  // Subscription details
  subscription: SubscriptionDetails | null;

  // Legacy /billing/me/ data (для обратной совместимости)
  billingMe: BillingMe | null;

  // States
  loading: boolean;
  error: string | null;

  // Methods
  refresh: () => Promise<void>;
  setAutoRenew: (enabled: boolean) => Promise<void>;

  // Computed properties
  isPro: boolean;
  isLimitReached: boolean;
}
```

#### 3.2 Обновите логику загрузки:

```typescript
const refresh = useCallback(async () => {
  if (!auth.isInitialized) {
    return;
  }

  try {
    setState(prev => ({ ...prev, loading: true, error: null }));

    // Загружаем ОБА эндпоинта параллельно
    const [subscriptionData, billingMeData] = await Promise.all([
      api.getSubscriptionDetails(),
      api.getBillingMe(), // Для лимитов фото
    ]);

    if (mounted.current) {
      setState({
        subscription: subscriptionData,
        billingMe: billingMeData,
        loading: false,
        error: null,
      });
    }
  } catch (error) {
    console.error('[BillingProvider] Failed to fetch data:', error);

    if (mounted.current) {
      setState(prev => ({
        ...prev,
        loading: false,
        error: error instanceof Error ? error.message : 'Failed to load billing data',
      }));
    }
  }
}, [auth.isInitialized]);

/**
 * Toggle auto-renew
 */
const setAutoRenew = useCallback(async (enabled: boolean) => {
  try {
    const updatedSubscription = await api.setAutoRenew(enabled);

    if (mounted.current) {
      setState(prev => ({
        ...prev,
        subscription: updatedSubscription,
      }));
    }
  } catch (error) {
    console.error('[BillingContext] Failed to toggle auto-renew:', error);
    throw error;
  }
}, []);
```

#### 3.3 Обновите computed properties:

```typescript
const isPro = useMemo(() => {
  return state.subscription?.plan === 'pro' && state.subscription?.is_active;
}, [state.subscription]);

const isLimitReached = useMemo(() => {
  const remaining = state.billingMe?.remaining_today;
  return remaining !== null && remaining !== undefined && remaining <= 0;
}, [state.billingMe]);
```

---

### 4. Обновить SettingsPage

Файл: `frontend/src/pages/SettingsPage.tsx`

#### 4.1 Обновите использование данных:

```typescript
const SettingsPage: React.FC = () => {
  const billing = useBilling();
  const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);

  const subscription = billing.subscription;

  // Проверки
  const isPro = subscription?.plan === 'pro';
  const expiresAt = subscription?.expires_at;
  const autoRenewEnabled = subscription?.autorenew_enabled ?? false;
  const autoRenewAvailable = subscription?.autorenew_available ?? false;
  const paymentMethod = subscription?.payment_method;
  const hasCard = paymentMethod?.is_attached ?? false;

  const handleToggleAutoRenew = async () => {
    if (togglingAutoRenew) return;

    if (!autoRenewAvailable) {
      showToast("Привяжите карту для включения автопродления");
      return;
    }

    try {
      setTogglingAutoRenew(true);
      await billing.setAutoRenew(!autoRenewEnabled);
      showToast(autoRenewEnabled ? "Автопродление отключено" : "Автопродление включено");
    } catch (error: any) {
      const message = error?.message || "Не удалось изменить настройки";
      showToast(message);
    } finally {
      setTogglingAutoRenew(false);
    }
  };

  // Форматирование даты
  const formatDate = (dateString: string | null) => {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'numeric',
      year: 'numeric'
    });
  };

  // Отображение карты
  const renderCardInfo = () => {
    if (!hasCard) {
      return <span>Карта не привязана</span>;
    }

    return (
      <>
        <CreditCard size={14} />
        <span>{paymentMethod.card_mask} · {paymentMethod.card_brand || 'Card'}</span>
      </>
    );
  };

  return (
    <div className="p-4 pb-24 space-y-6 bg-gray-50 min-h-screen">
      {/* ... существующий UI ... */}

      {/* Tariff Status */}
      <div className="p-4 border-b border-gray-100 flex justify-between items-center">
        <span className="text-gray-900">Тариф</span>
        <span className="text-gray-500 font-medium">
          {isPro ? `PRO до ${formatDate(expiresAt)}` : 'Free'}
        </span>
      </div>

      {/* Auto-renew Toggle */}
      <div className="p-4 border-b border-gray-100 space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-gray-900">Автопродление PRO</span>
          <button
            onClick={handleToggleAutoRenew}
            disabled={togglingAutoRenew || !autoRenewAvailable}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              autoRenewEnabled ? 'bg-green-500' : 'bg-gray-200'
            } ${(!autoRenewAvailable || togglingAutoRenew) ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                autoRenewEnabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
        <p className="text-xs text-gray-400 leading-relaxed">
          {autoRenewAvailable ? (
            autoRenewEnabled
              ? "Ежемесячное списание через привязанную карту."
              : "Списание не выполняется. Доступ к PRO сохранится до конца оплаченного периода."
          ) : (
            "Автопродление недоступно — привяжите карту в разделе «Способ оплаты»."
          )}
        </p>
      </div>

      {/* Payment Method */}
      <div className="p-4 flex justify-between items-center">
        <div className="space-y-1">
          <span className="text-gray-900 block">Способ оплаты</span>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            {renderCardInfo()}
          </div>
        </div>
        <ChevronRight size={20} className="text-gray-300" />
      </div>
    </div>
  );
};
```

---

### 5. Добавить страницу истории платежей (опционально)

Создайте новый файл: `frontend/src/pages/PaymentHistoryPage.tsx`

```typescript
import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { PaymentHistoryItem } from '../types/billing';

const PaymentHistoryPage: React.FC = () => {
  const [payments, setPayments] = useState<PaymentHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadPayments();
  }, []);

  const loadPayments = async () => {
    try {
      setLoading(true);
      const { results } = await api.getPaymentsHistory(20);
      setPayments(results);
    } catch (error) {
      console.error('Failed to load payments:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const badges = {
      succeeded: 'bg-green-100 text-green-800',
      pending: 'bg-yellow-100 text-yellow-800',
      failed: 'bg-red-100 text-red-800',
      canceled: 'bg-gray-100 text-gray-800',
      refunded: 'bg-blue-100 text-blue-800',
    };
    return badges[status as keyof typeof badges] || badges.pending;
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleDateString('ru-RU', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (loading) {
    return (
      <div className="p-4 text-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
      </div>
    );
  }

  return (
    <div className="p-4 pb-24 space-y-4 bg-gray-50 min-h-screen">
      <h1 className="text-2xl font-bold">История оплат</h1>

      {payments.length === 0 ? (
        <div className="text-center text-gray-500 py-8">
          Нет платежей
        </div>
      ) : (
        <div className="space-y-3">
          {payments.map((payment) => (
            <div
              key={payment.id}
              className="bg-white rounded-xl p-4 shadow-sm"
            >
              <div className="flex justify-between items-start mb-2">
                <div>
                  <div className="font-medium">{payment.description}</div>
                  <div className="text-sm text-gray-500">
                    {formatDate(payment.paid_at)}
                  </div>
                </div>
                <div className="text-right">
                  <div className="font-bold">
                    {payment.amount} {payment.currency}
                  </div>
                  <span
                    className={`text-xs px-2 py-1 rounded-full ${getStatusBadge(payment.status)}`}
                  >
                    {payment.status}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default PaymentHistoryPage;
```

---

## Тестирование после интеграции

### 1. Проверка подписки Free пользователя:

```bash
# В консоли браузера
const billing = await fetch('/api/v1/billing/subscription/', {
  headers: { 'X-Telegram-Init-Data': window.Telegram.WebApp.initData }
}).then(r => r.json());

console.log(billing);
// Ожидается:
// {
//   plan: 'free',
//   plan_display: 'Free',
//   expires_at: null,
//   is_active: true,
//   autorenew_available: false,
//   autorenew_enabled: false,
//   payment_method: { is_attached: false, card_mask: null, card_brand: null }
// }
```

### 2. Проверка toggle автопродления:

```bash
const result = await fetch('/api/v1/billing/subscription/autorenew/', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Telegram-Init-Data': window.Telegram.WebApp.initData
  },
  body: JSON.stringify({ enabled: true })
}).then(r => r.json());

console.log(result);
```

### 3. Проверка истории платежей:

```bash
const history = await fetch('/api/v1/billing/payments/?limit=5', {
  headers: { 'X-Telegram-Init-Data': window.Telegram.WebApp.initData }
}).then(r => r.json());

console.log(history.results);
```

---

## Деплой обновлений

### 1. Локальная разработка:

```bash
cd frontend
npm run dev
```

### 2. Production build:

```bash
cd frontend
npm run build
```

### 3. Деплой на сервер:

```bash
# Если используется Docker
cd /opt/foodmind
git pull origin main
docker restart fm-frontend
```

---

## Checklist перед деплоем

- [ ] TypeScript типы добавлены
- [ ] API методы реализованы
- [ ] BillingContext обновлен
- [ ] SettingsPage использует новые данные
- [ ] Локальное тестирование пройдено
- [ ] Build без ошибок
- [ ] Тестирование на проде

---

## Troubleshooting

### Проблема: TypeError: Cannot read property 'plan' of null

**Причина:** `subscription` еще не загружен

**Решение:** Добавьте проверки:
```typescript
const isPro = subscription?.plan === 'pro' ?? false;
```

### Проблема: 401 Unauthorized

**Причина:** Нет заголовков аутентификации

**Решение:** Проверьте, что `getHeaders()` правильно формирует заголовки с `initData`

### Проблема: Автопродление не включается

**Причина:** Нет привязанной карты

**Решение:** Сначала нужно оплатить подписку с `save_payment_method=true`

---

## Дополнительные ресурсы

- [Backend API Documentation](billing-settings-api.md)
- [Manual Testing Checklist](billing_manual_test.md)
- [Implementation Summary](BILLING_IMPLEMENTATION_SUMMARY.md)
