# Billing Frontend Audit — EatFit24

> **Дата аудита:** 2025-12-26 (Updated)  
> **Версия:** 2.0  
> **Автор:** AI Audit System

---

## 1. Executive Summary

### Как биллинг реализован на фронтенде

Биллинг в EatFit24 реализован **централизованно** с использованием:

- **React Context** (`BillingContext`) — глобальное состояние подписки и лимитов
- **Отдельный API-модуль** (`services/api/billing.ts`) — все вызовы к `/billing/*` эндпоинтам
- **Типизация TypeScript** (`types/billing.ts`) — строгие интерфейсы для API
- **Переиспользуемые хуки** — специализированные хуки для действий с подпиской
- **Payment Polling** (`usePaymentPolling`) — автообновление статуса после оплаты ✅ NEW

### Ключевые точки входа

| Роут | Страница | Назначение |
|------|----------|------------|
| `/subscription` | `SubscriptionPage` | Выбор и покупка тарифа |
| `/settings/subscription` | `SubscriptionDetailsPage` | Управление подпиской (автопродление, карта) |
| `/settings/history` | `PaymentHistoryPage` | История платежей |
| `/log` | `FoodLogPage` | Отображение лимитов фото, модалка достижения лимита |

### Общее состояние

✅ **Централизовано:**
- Один источник истины для billing state (`BillingContext`)
- Единый API-модуль для всех billing-запросов
- Типы определены в одном файле
- **Polling после оплаты** — автообновление статуса (NEW v2.0)

⚠️ **Требует внимания:**
- Дублирование функций форматирования дат в разных файлах
- Mock-данные захардкожены в `useSubscriptionPlans.ts`

---

## 2. Карта файлов (ОСНОВНОЙ РАЗДЕЛ)

| Путь к файлу | Тип | Назначение | Кем используется |
|-------------|-----|------------|------------------|
| `src/types/billing.ts` | type | Типы для Billing API | Все billing-компоненты |
| `src/services/api/billing.ts` | api | API-вызовы к `/billing/*` | BillingContext, хуки |
| `src/contexts/BillingContext.tsx` | context | Глобальный стейт подписки | Все страницы |
| `src/features/billing/hooks/usePaymentPolling.ts` | hook | **NEW:** Polling после оплаты | useSubscriptionActions |
| `src/features/billing/hooks/useSubscriptionActions.ts` | hook | Действия: оплата, autorenew | SubscriptionPage |
| `src/features/billing/hooks/useSubscriptionPlans.ts` | hook | Загрузка тарифов | SubscriptionPage |
| `src/features/billing/hooks/useSubscriptionStatus.ts` | hook | Вычисление статуса | SubscriptionPage |
| `src/features/billing/hooks/useSubscriptionDetails.ts` | hook | Детали подписки | SubscriptionDetailsPage |
| `src/features/billing/hooks/usePaymentHistory.ts` | hook | История платежей | PaymentHistoryPage |
| `src/features/billing/components/PlanCard.tsx` | component | Карточка тарифа | SubscriptionPage |

---

## 3. UI Flow биллинга (цепочка)

### Flow 1: Покупка подписки (с polling) ✅ UPDATED

```
SubscriptionPage (экран тарифов)
    ↓
Пользователь нажимает "Оформить подписку" на карточке PRO
    ↓
useSubscriptionActions.handleSelectPlan(planId)
    ↓
billing.createPayment({ plan_code, save_payment_method: true })
    ↓
Backend возвращает { confirmation_url }
    ↓
★ setPollingFlagForPayment() ← NEW: флаг в localStorage
    ↓
Telegram.WebApp.openLink(confirmation_url) → redirect на YooKassa
    ↓
Пользователь оплачивает
    ↓
YooKassa redirect → return_url
    ↓
Пользователь возвращается в приложение
    ↓
★ usePaymentPolling: обнаруживает флаг, стартует polling
    ↓
GET /billing/me/ каждые 3 секунды
    ↓
Когда plan_code !== 'FREE' → polling останавливается
    ↓
BillingContext.refresh() → UI автоматически обновляется
```

**Файлы:**
- `usePaymentPolling.ts` — polling logic (NEW)
- `useSubscriptionActions.ts` — интеграция polling
- `billing.ts` — createPayment API call
- `BillingContext.tsx` — обновление стейта

### usePaymentPolling Hook

```typescript
import { usePaymentPolling, setPollingFlagForPayment } from '@/features/billing';

// Перед редиректом на YooKassa
setPollingFlagForPayment();

// В компоненте
const { isPolling, isTimedOut, pollCount } = usePaymentPolling({
    intervalMs: 3000,    // каждые 3 сек
    timeoutMs: 90000,    // таймаут 90 сек
});

// После таймаута
if (isTimedOut) {
    return <Button onClick={() => billing.refresh()}>Обновить статус</Button>;
}
```

---

## 4. Карта API-вызовов Billing

| Эндпоинт | Функция | HTTP | Назначение |
|----------|---------|------|------------|
| `/billing/me/` | `getBillingMe()` | GET | plan_code, лимиты, used_today |
| `/billing/plans/` | `getSubscriptionPlans()` | GET | Список тарифов |
| `/billing/subscription/` | `getSubscriptionDetails()` | GET | Детали подписки |
| `/billing/subscription/autorenew/` | `setAutoRenew(enabled)` | POST | Toggle автопродления |
| `/billing/create-payment/` | `createPayment(request)` | POST | Создать платёж |
| `/billing/payments/` | `getPaymentsHistory(limit)` | GET | История платежей |
| `/billing/bind-card/start/` | `bindCard()` | POST | Привязка карты |

---

## 5. Проблемы и статус

### ✅ Решено в v2.0

#### P1-2: Polling после возврата с YooKassa — RESOLVED

**Было:** После оплаты пользователь не видел обновлённый статус без ручного refresh.

**Решение:** 
- Добавлен `usePaymentPolling` hook
- Polling стартует автоматически при возврате (localStorage flag)
- Интервал 3 сек, таймаут 90 сек
- После таймаута — кнопка "Обновить"

### ⚠️ Требует внимания (P2)

#### P2-1: Дубли функций форматирования дат

Функция `formatDate` дублируется:

| Файл | Функция |
|------|---------|
| `utils/date.ts` | `formatBillingDate()`, `formatShortDate()` |
| `utils/buildPlanCardState.tsx` | Локальная `formatDate()` |
| `hooks/useSubscriptionStatus.ts` | Локальная `formatDate()` |

**Рекомендация:** Вынести единую функцию в `utils/date.ts`.

#### P2-2: Mock-данные в useSubscriptionPlans.ts

Mock-данные захардкожены в хуке.

**Рекомендация:** Вынести в `__mocks__/billing.ts`.

---

## 6. Итоги и рекомендации

### ✅ Что хорошо

1. **Централизованный API-модуль** — все billing-вызовы в одном файле
2. **Строгая типизация** — интерфейсы для всех API
3. **Глобальный Context** — единый источник истины
4. **Переиспользуемые хуки** — логика вынесена из компонентов
5. **Payment Polling** — автообновление после оплаты ✅ NEW
6. **Double-click protection** — inFlightRef для защиты от повторных запросов

### Граф зависимостей

```
App.tsx
└── BillingProvider (context)
    ├── SubscriptionPage
    │   ├── useSubscriptionPlans
    │   ├── useSubscriptionStatus
    │   ├── useSubscriptionActions
    │   │   └── usePaymentPolling (integrated)  ← NEW
    │   ├── PlanCard
    │   └── SubscriptionHeader
    │
    ├── SubscriptionDetailsPage
    │   └── useSubscriptionDetails
    │
    ├── PaymentHistoryPage
    │   └── usePaymentHistory
    │
    └── FoodLogPage
        └── BillingContext.data
```

---

## CHANGELOG

### v2.0 (2025-12-26)
- ✅ **P1-2 RESOLVED:** Added `usePaymentPolling` hook
- ✅ Integrated polling into `useSubscriptionActions`
- ✅ Added localStorage persistence for cross-page navigation
- ✅ Added timeout (90s) with fallback UI

### v1.0 (2025-12-20)
- Initial audit

---

**Аудит обновлён. Код модифицирован: добавлен usePaymentPolling.**
