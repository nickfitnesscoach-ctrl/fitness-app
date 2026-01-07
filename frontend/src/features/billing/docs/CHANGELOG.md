# CHANGELOG — Billing Feature Module

> История изменений модуля биллинга.

---

## [2.1.0] — 2026-01-06

### 🎨 UI Refinements

**Унификация карточек тарифных планов**

Реализована новая архитектура UI-компонентов для стабильного и консистентного отображения тарифных планов на всех устройствах.

### ✨ Features

- **Presentational Card Components**
  - `BasicPlanCard.tsx` — карточка FREE плана с минималистичным дизайном
  - `PremiumMonthCard.tsx` — карточка PRO_MONTHLY с темным градиентом
  - `PremiumProCard.tsx` — карточка PRO_YEARLY с badge "2 МЕСЯЦА В ПОДАРОК"
  
- **PlanPriceStack Component**
  - Унифицированный компонент для отображения цен
  - Стабильный 2-row layout предотвращает "прыгающие" блоки на мобильных
  - Поддержка fixed min-height для oldPrice и priceSubtext
  - Табулярные числа для корректного выравнивания

- **Text Processing Utilities (`utils/text.tsx`)**
  - `cleanFeatureText()` — очистка emoji, replacement chars, zero-width chars из текста фич
  - `getPlanFeatureIcon()` — семантическое определение иконок по содержанию текста (не по emoji)
  - Поддержка Cyrillic и полезных символов

- **Enhanced Card State Logic**
  - Улучшенная функция `buildPlanCardState()` в `utils/planCardState.tsx`
  - Корректная обработка состояний: current, disabled, expired, loading
  - Динамический `bottomContent` для PRO-карточек с информацией об автопродлении

### 🐛 Bug Fixes

- Исправлена проблема с "прыгающими" ценовыми блоками на iPhone и Android
- Удалены emoji и спецсимволы из feature-текстов для чистого отображения
- Унифицированы иконки — теперь определяются по семантике, а не по emoji в исходных данных
- Явное приведение `isButtonDisabled` к boolean через `Boolean()` во всех карточках

### 🔧 Components Architecture

- **Orchestrator Pattern**: `PlanCard.tsx` — умный компонент, управляет состоянием и логикой
- **Presentational Components**: `BasicPlanCard`, `PremiumMonthCard`, `PremiumProCard` — чистые UI-компоненты
- **Shared Price Component**: `PlanPriceStack` — переиспользуемый компонент цен

### 📝 Documentation

- Обновлён `FILE_MAP.md` с новыми компонентами и утилитами
- Обновлён этот `CHANGELOG.md` с версией 2.1.0

---

## [2.0.0] — 2025-12-20

### 🏗️ BREAKING CHANGES

- **Удалены legacy plan codes:** `MONTHLY` и `YEARLY`
  - `BillingPlanCode` теперь строго `'FREE' | 'PRO_MONTHLY' | 'PRO_YEARLY'`
  - `PLAN_CODES.MONTHLY` и `PLAN_CODES.YEARLY` удалены
  
- **Удалена функция `normalizePlanCode()`**
  - Была в `constants/index.ts`
  - Заменена на `validatePlanCode()` в `utils/validation.ts`

### ✨ Features

- **Feature-модуль `src/features/billing/`**
  - Изолированный домен для всего биллинга
  - Barrel export через `index.ts`

- **Anti-double-click защита**
  - Все payment actions защищены через `useRef<Set<string>>`
  - Защищены: createPayment, bindCard, toggleAutoRenew, testPayment

- **Strict plan_code validation**
  - `assertBillingPlanCode()` — type guard
  - `validatePlanCode()` — валидация с fallback на FREE

- **Unified notification utility**
  - `showToast()` — единый helper для Telegram/browser
  - Удалены дубли в хуках

- **Unified date formatting**
  - `formatBillingDate()`, `formatShortDate()`, `formatDate()` в одном файле
  - Удалены локальные дубли

- **Mock планы вынесены**
  - `__mocks__/plans.ts` — отдельный файл для DEV

### 📄 Documentation

- `README.md` — обзор модуля
- `FILE_MAP.md` — карта файлов
- `ROUTES.md` — описание маршрутов
- `API_CONTRACT.md` — контракты API
- `UI_FLOWS.md` — пользовательские сценарии
- `STATE_MODEL.md` — модель состояния
- `ERROR_HANDLING.md` — обработка ошибок
- `DEV_NOTES.md` — заметки для разработчиков
- `CHANGELOG.md` — история изменений

### 📁 Файлы перенесены

**Из `src/pages/`:**
- `SubscriptionPage.tsx`
- `SubscriptionDetailsPage.tsx`
- `PaymentHistoryPage.tsx`

**Из `src/components/`:**
- `PlanCard.tsx`
- `subscription/SubscriptionHeader.tsx`
- `billing/AdminTestPaymentCard.tsx`
- `billing/PaymentHistoryList.tsx`

**Из `src/hooks/`:**
- `useSubscriptionPlans.ts`
- `useSubscriptionStatus.ts`
- `useSubscriptionActions.ts`
- `useSubscriptionDetails.ts`
- `usePaymentHistory.ts`

**Из `src/utils/`:**
- `date.ts` (скопирован)
- `buildPlanCardState.tsx` → `planCardState.tsx`

### 🔧 Изменённые файлы

- `src/types/billing.ts` — сужен `BillingPlanCode`
- `src/constants/index.ts` — удалены legacy коды и `normalizePlanCode()`
- `src/App.tsx` — импорты обновлены на feature module

### 🗑️ Файлы к удалению (старые)

После верификации можно удалить:
- `src/pages/SubscriptionPage.tsx`
- `src/pages/SubscriptionDetailsPage.tsx`
- `src/pages/PaymentHistoryPage.tsx`
- `src/components/PlanCard.tsx`
- `src/components/subscription/` (пусто)
- `src/components/billing/` (пусто)
- `src/hooks/useSubscriptionPlans.ts`
- `src/hooks/useSubscriptionStatus.ts`
- `src/hooks/useSubscriptionActions.ts`
- `src/hooks/useSubscriptionDetails.ts`
- `src/hooks/usePaymentHistory.ts`
- `src/utils/buildPlanCardState.tsx`

---

## [1.0.0] — До рефакторинга

- Файлы распределены по `pages/`, `components/`, `hooks/`, `utils/`
- Legacy plan codes `MONTHLY`, `YEARLY` с `normalizePlanCode()`
- Дублирование `formatDate` и `showToast` в разных файлах
- Mock данные захардкожены в `useSubscriptionPlans.ts`
- Нет anti-double-click защиты
