# Billing Feature Module

> **Изолированный домен биллинга EatFit24** — управление подписками, платежами, лимитами и тарифами.

---

## Содержание

- [Назначение](#назначение)
- [Архитектура](#архитектура)
- [Файловая структура](#файловая-структура)
- [Типы и SSOT](#типы-и-ssot)
- [Публичный API](#публичный-api)
- [Маршруты](#маршруты)
- [Компоненты](#компоненты)
- [Hooks](#hooks)
- [Утилиты](#утилиты)
- [Схема работы платежей](#схема-работы-платежей)
- [Тестирование](#тестирование)
- [Импорты](#примеры-импортов)

---

## Назначение

Модуль отвечает за:

| Область | Описание |
|---------|----------|
| **Тарифные планы** | Отображение и выбор FREE / PRO_MONTHLY / PRO_YEARLY |
| **Подписка** | Управление автопродлением, привязка карты |
| **Платежи** | Создание, поллинг статуса, история |
| **Лимиты** | Daily limits для AI-распознавания фото |

---

## Архитектура

```
┌─────────────────────────────────────────────────────────────┐
│                    BillingContext (глобальный)              │
├─────────────────────────────────────────────────────────────┤
│  subscription: SubscriptionDetails  │  billingMe: BillingMe │
│  ├─ is_active                       │  ├─ plan_code         │
│  ├─ autorenew_enabled               │  ├─ daily_photo_limit │
│  ├─ payment_method                  │  ├─ used_today        │
│  └─ expires_at                      │  └─ remaining_today   │
├─────────────────────────────────────────────────────────────┤
│  isPro: boolean    │    isLimitReached: boolean              │
│  refresh()         │    setAutoRenew()    │    addPaymentMethod() │
└─────────────────────────────────────────────────────────────┘
           │                              │
           ▼                              ▼
   GET /billing/subscription/    GET /billing/me/
```

**Источники данных:**

| Endpoint | Данные | Использование |
|----------|--------|---------------|
| `GET /billing/me/` | `plan_code`, лимиты | Точный тариф, оставшиеся фото |
| `GET /billing/subscription/` | Статус подписки | is_active, autorenew, payment_method |

---

## Файловая структура

```
features/billing/
├── index.ts              # Публичный API модуля
├── internal.ts           # Внутренние экспорты (только для billing)
├── types.ts              # SSOT: PlanCode, PLAN_CODES, type guards
│
├── pages/
│   ├── SubscriptionPage.tsx        # /subscription — выбор плана
│   ├── SubscriptionDetailsPage.tsx # /settings/subscription — управление
│   └── PaymentHistoryPage.tsx      # /settings/history — история
│
├── components/
│   ├── PlanCard.tsx            # Роутер: выбирает карточку по plan.code
│   ├── BasicPlanCard.tsx       # FREE план
│   ├── PremiumMonthCard.tsx    # PRO_MONTHLY план
│   ├── PremiumProCard.tsx      # PRO_YEARLY план
│   ├── PlanPriceStack.tsx      # Стабильный UI цены (2-row layout)
│   ├── SubscriptionHeader.tsx  # Заголовок страницы
│   ├── PaymentHistoryList.tsx  # Список платежей
│   └── AdminTestPaymentCard.tsx# Тестовый платёж (только админы)
│
├── hooks/
│   ├── useSubscriptionPlans.ts    # Загрузка списка тарифов
│   ├── useSubscriptionStatus.ts   # Текущий статус подписки
│   ├── useSubscriptionActions.ts  # Действия: купить, toggle autorenew
│   ├── useSubscriptionDetails.ts  # Детали для страницы управления
│   ├── usePaymentHistory.ts       # История платежей
│   └── usePaymentPolling.ts       # Поллинг статуса платежа
│
├── utils/
│   ├── planCardState.tsx  # buildPlanCardState — логика состояния карточек
│   ├── date.ts            # formatBillingDate, formatShortDate
│   ├── notify.ts          # showToast, showSuccess, showError
│   ├── text.tsx           # cleanFeatureText, getPlanFeatureIcon
│   └── validation.ts      # Дополнительные валидаторы
│
├── __mocks__/
│   └── plans.ts           # Mock-данные для DEV режима
│
└── docs/
    └── README.md          # (этот файл)
```

---

## Типы и SSOT

Все определения типов живут в **`types.ts`** — единственный источник истины.

### PlanCode (основной тип)

```typescript
// Константа — массив всех валидных кодов
export const PLAN_CODES = ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'] as const;

// Тип — union из константы
export type PlanCode = (typeof PLAN_CODES)[number];

// Порядок отображения в UI
export const PLAN_CODE_ORDER: readonly PlanCode[] = ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'];
```

### Type Guards

```typescript
// Проверка: является ли значение валидным PlanCode
isPlanCode(value: unknown): value is PlanCode

// Безопасное преобразование с fallback на 'FREE'
toPlanCodeOrFree(value: unknown): PlanCode

// Проверка PRO-тарифа
isProPlanCode(code: PlanCode): boolean  // PRO_MONTHLY | PRO_YEARLY
```

> [!IMPORTANT]
> Никогда не создавайте локальные типы для plan codes.
> Всегда импортируйте из `features/billing/types` или `features/billing`.

---

## Публичный API

### index.ts — публичные экспорты

```typescript
// Pages
export { SubscriptionPage, SubscriptionDetailsPage, PaymentHistoryPage }

// Hooks
export {
  useSubscriptionPlans,
  useSubscriptionStatus,
  useSubscriptionActions,
  useSubscriptionDetails,
  usePaymentHistory,
  usePaymentPolling,
  setPollingFlagForPayment,
  clearPollingFlag
}

// Types (SSOT)
export type { PlanCode }
export { PLAN_CODES, PLAN_CODE_ORDER, isPlanCode, toPlanCodeOrFree, isProPlanCode }

// Utils
export { formatBillingDate, formatShortDate, formatDate }
export { showToast, showSuccess, showError }

// Components
export { PlanCard, SubscriptionHeader }
export { buildPlanCardState, AdminTestPaymentCard, PaymentHistoryList }
```

### internal.ts — внутренние экспорты

Для использования **только внутри billing**:

```typescript
export { BasicPlanCard, PremiumMonthCard, PremiumProCard }
```

---

## Маршруты

| Роут | Страница | Назначение |
|------|----------|------------|
| `/subscription` | `SubscriptionPage` | Выбор и покупка тарифа |
| `/settings/subscription` | `SubscriptionDetailsPage` | Управление подпиской |
| `/settings/history` | `PaymentHistoryPage` | История платежей |

---

## Компоненты

### PlanCard (роутер)

Не рендерит UI напрямую — выбирает нужную карточку по `plan.code`:

```
plan.code → PlanCard → BasicPlanCard | PremiumMonthCard | PremiumProCard
```

### Презентационные карточки

| Карточка | Plan Code | Особенности |
|----------|-----------|-------------|
| `BasicPlanCard` | FREE | Минималистичный дизайн |
| `PremiumMonthCard` | PRO_MONTHLY | Акцентный дизайн, "Попробовать PRO" |
| `PremiumProCard` | PRO_YEARLY | "POPULAR" badge, старая цена, "≈ N ₽/мес" |

### PlanPriceStack

Стабильный 2-row layout для цены:

```
Row 1: старая цена (зачёркнутая) или пустота
Row 2: подпись ("≈ 208 ₽/мес") или пустота
```

Исключает layout shifts при различных данных.

---

## Hooks

| Hook | Назначение |
|------|------------|
| `useSubscriptionPlans` | Загружает список тарифов из API или mocks |
| `useSubscriptionStatus` | Возвращает isPro, isExpired, currentPlanCode |
| `useSubscriptionActions` | handleSelectPlan, handleToggleAutoRenew, handleAddCard |
| `useSubscriptionDetails` | Полные данные для страницы управления подпиской |
| `usePaymentHistory` | Загружает историю платежей |
| `usePaymentPolling` | Поллинг статуса после редиректа с YooKassa |

### useSubscriptionActions — безопасность

```typescript
// Allowlist для платёжных URL (защита от фишинга)
const PAYMENT_URL_ALLOWLIST = [
  'yookassa.ru',
  'checkout.yookassa.ru',
  'yoomoney.ru',
];
```

---

## Утилиты

### planCardState.tsx

Главная функция `buildPlanCardState()` определяет состояние карточки:

```typescript
interface PlanCardState {
  isCurrent: boolean;      // Это текущий план пользователя?
  disabled: boolean;       // Кнопка заблокирована?
  customButtonText?: string;  // Текст кнопки
  bottomContent?: ReactNode;  // Дополнительный контент снизу
}
```

**SSOT для данных:**
- `billing.subscription` → статус подписки
- `billing.billingMe` → точный план (plan_code)

### date.ts

```typescript
formatBillingDate(date)  // "20 дек. 2025, 14:30"
formatShortDate(date)    // "20.12.2025"
formatDate(date)         // alias для formatShortDate
```

### notify.ts

```typescript
showToast(message)   // Telegram WebApp.showAlert или browser alert
showSuccess(message) // Семантический alias
showError(message)   // Семантический alias
```

### text.tsx

```typescript
cleanFeatureText(input)      // Убирает эмодзи, replacement chars
getPlanFeatureIcon(text)     // Иконка по смыслу текста (AI → Zap, КБЖУ → Calculator)
```

---

## Схема работы платежей

```
┌─────────────┐     ┌────────────┐     ┌───────────┐
│  Frontend   │────▶│  Backend   │────▶│  YooKassa │
│ createPay() │     │ /payments/ │     │           │
└─────────────┘     └────────────┘     └───────────┘
       │                                     │
       │ ◀──── confirmation_url ◀────────────┤
       │                                     │
       ▼                                     │
┌─────────────┐                              │
│  Redirect   │  (пользователь оплачивает)   │
│  to YooKassa│                              │
└─────────────┘                              │
       │                                     │
       │                              webhook │
       │                                     ▼
       │                           ┌────────────┐
       │                           │  Backend   │
       │                           │ обновляет  │
       │                           │ подписку   │
       │                           └────────────┘
       │                                     │
       ▼                                     │
┌─────────────┐                              │
│  Return URL │ ◀────────────────────────────┘
│ (frontend)  │
└─────────────┘
       │
       ▼
┌─────────────┐
│ usePayment- │   Поллинг /billing/subscription/
│ Polling     │   пока статус не станет active
└─────────────┘
       │
       ▼
┌─────────────┐
│ BillingCtx  │
│ .refresh()  │   Обновление глобального состояния
└─────────────┘
```

**Важно:** Фронтенд НЕ полагается на прямой ответ от YooKassa.
Webhook-first = бэкенд — единственный источник истины о статусе подписки.

---

## Тестирование

### DEV режим (mock данные)

При `IS_DEV=true` хук `useSubscriptionPlans` использует данные из `__mocks__/plans.ts`.

### Проверка маршрутов

```bash
npm run dev

# Проверить:
# http://localhost:5173/app/subscription
# http://localhost:5173/app/settings/subscription
# http://localhost:5173/app/settings/history
```

### Тестовый платёж (Admin)

На `/settings/subscription` для админов доступна карточка **"Тест: Оплатить 1₽ (live)"**.

Условие отображения: `billingMe.test_live_payment_available === true`.

### Typecheck

```bash
npx tsc --noEmit
```

---

## Примеры импортов

### Для внешнего кода (pages, другие features)

```typescript
// Pages
import { SubscriptionPage, SubscriptionDetailsPage } from 'features/billing';

// Hooks
import {
  useSubscriptionPlans,
  useSubscriptionActions,
  useSubscriptionDetails,
  usePaymentPolling
} from 'features/billing';

// Types
import type { PlanCode } from 'features/billing';
import { PLAN_CODES, isPlanCode, toPlanCodeOrFree, isProPlanCode } from 'features/billing';

// Utils
import { formatBillingDate, showToast } from 'features/billing';

// Components
import { PlanCard, SubscriptionHeader } from 'features/billing';
```

### Для кода внутри billing

```typescript
// Используйте относительные импорты
import { isPlanCode, type PlanCode } from '../types';
import { buildPlanCardState } from '../utils/planCardState';
import { BasicPlanCard } from './BasicPlanCard';

// Или через internal.ts
import { BasicPlanCard, PremiumMonthCard } from '../internal';
```

---

## Связанная документация

Архивные документы (могут быть устаревшими):

- `docs/archive/ERROR_HANDLING.md` — обработка ошибок
- `docs/archive/DEV_NOTES.md` — заметки разработчика

---

> **Версия документации:** 2025-01-13
>
> **SSOT файл:** `features/billing/types.ts`
