# STATE MODEL — Billing Feature Module

> Модель состояния биллинга в приложении.

---

## BillingContext

Глобальный контекст для управления состоянием подписки.

### Хранимые поля

```typescript
interface BillingContextType {
    // Детали подписки (из GET /billing/subscription/)
    subscription: SubscriptionDetails | null;
    
    // Данные лимитов (из GET /billing/me/)
    billingMe: BillingMe | null;
    
    // Состояния загрузки
    loading: boolean;
    error: string | null;
    
    // Вычисляемые флаги
    isPro: boolean;           // subscription?.plan === 'pro' && is_active
    isLimitReached: boolean;  // remaining_today <= 0
    
    // Методы
    refresh: () => Promise<void>;
    setAutoRenew: (enabled: boolean) => Promise<void>;
    toggleAutoRenew: (enable: boolean) => Promise<void>; // alias
    addPaymentMethod: () => Promise<void>;
    
    // Legacy alias
    data: BillingMe | null;   // = billingMe
}
```

---

## Источники данных

### GET /billing/me/

Используется для:
- `plan_code` — текущий тариф
- `daily_photo_limit` / `used_today` / `remaining_today` — лимиты
- `expires_at` — дата истечения
- `test_live_payment_available` — флаг для админов

### GET /billing/subscription/

Используется для:
- `plan` — тип плана ('free' | 'pro')
- `autorenew_enabled` / `autorenew_available` — автопродление
- `payment_method` — информация о привязанной карте
- `expires_at` — дата истечения

---

## Когда вызывается refresh()

1. **При инициализации** — `useEffect` в `BillingProvider` после `auth.isInitialized`
2. **После привязки карты** — в `addPaymentMethod()`
3. **При возврате с платёжной страницы** — пользователь вручную открывает app
4. **При необходимости** — любой компонент может вызвать `useBilling().refresh()`

---

## Derived Flags

### isPro

```typescript
const isPro = useMemo(() => {
    return state.subscription?.plan === 'pro' && state.subscription?.is_active;
}, [state.subscription]);
```

### isLimitReached

```typescript
const isLimitReached = useMemo(() => {
    const remaining = state.billingMe?.remaining_today;
    return remaining !== null && remaining !== undefined && remaining <= 0;
}, [state.billingMe]);
```

---

## Процесс загрузки

```
App mount
    ↓
AuthProvider initializes
    ↓
auth.isInitialized = true
    ↓
BillingProvider.useEffect triggers
    ↓
BillingContext.refresh()
    ↓
Promise.all([
    api.getSubscriptionDetails(),
    api.getBillingMe()
])
    ↓
setState({ subscription, billingMe, loading: false })
```

---

## Локальное состояние в хуках

### useSubscriptionActions

```typescript
const [loadingPlanId, setLoadingPlanId] = useState<PlanId | null>(null);
const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);
const inFlightRef = useRef<Set<string>>(new Set());  // Anti-double-click
```

### useSubscriptionDetails

```typescript
const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);
const [creatingTestPayment, setCreatingTestPayment] = useState(false);
const inFlightRef = useRef<Set<string>>(new Set());  // Anti-double-click
```

---

## Plan Card State Logic

### buildPlanCardState()

Функция в `utils/planCardState.tsx` определяет визуальное состояние каждой карточки плана.

#### Интерфейсы

```typescript
interface PlanCardState {
    isCurrent: boolean;           // Это текущий план пользователя
    disabled: boolean;            // Кнопка неактивна
    customButtonText?: string;    // Кастомный текст кнопки
    bottomContent?: React.ReactNode;  // Дополнительный контент под кнопкой
}

interface BuildPlanCardStateParams {
    plan: SubscriptionPlan;
    subscription: SubscriptionDetails | null;
    billing: BillingContextData;
    isPro: boolean;
    isExpired: boolean;
    expiresAt: string | null;
    loadingPlanCode: PlanCode | null;
    togglingAutoRenew: boolean;
    handleSelectPlan: (planCode: PlanCode) => void;
    handleToggleAutoRenew: () => void;
    handleAddCard: () => void;
    navigate: (path: string) => void;
}
```

#### Логика определения состояния

1. **FREE карточка:**
   - Если у пользователя PRO → `disabled=true`, `customButtonText="Базовый доступ"`
   - Если у пользователя FREE → `isCurrent=true`, `customButtonText="Ваш текущий тариф"`

2. **PRO карточки (когда PRO активен, но plan_code неизвестен):**
   - `disabled=true`, `customButtonText="PRO активен"`
   - `bottomContent` — информация о сроке, автопродлении, карте

3. **PRO карточка точного плана (userPlanCode === planCode):**
   - `isCurrent=true`
   - `bottomContent` — полная информация с кнопками управления:
     - Autorenew активно → показать карту и ссылку "Управлять подпиской"
     - Autorenew выключено → кнопка "Включить продление"
     - Карта не привязана → кнопка "Привязать карту"

4. **Другой PRO план (isPro, но другой plan_code):**
   - `disabled=true`, `customButtonText="Доступно по подписке"`

5. **Expired план:**
   - `bottomContent` — warning + кнопка "Восстановить за [price]₽"

---

## Инварианты

1. **Один источник истины** — `BillingContext` хранит всё
2. **Синхронизация с бэкендом** — refresh() после мутаций
3. **Optimistic updates** — не используются (webhook-first архитектура)
4. **plan_code** — строго `FREE | PRO_MONTHLY | PRO_YEARLY`
