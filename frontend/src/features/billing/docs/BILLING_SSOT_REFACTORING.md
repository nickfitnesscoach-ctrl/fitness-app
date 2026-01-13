# Billing SSOT Refactoring — Walkthrough

## Summary

Billing-модуль приведён к единому источнику истины (SSOT) по типам и контрактам.  
Удалены дубли, прояснены зоны ответственности данных, публичный API модуля формализован.  
**Поведение продукта не изменено.**

---

## Changes Made

### 1. Billing SSOT Types

Создан единый канонический источник для кодов тарифов:  
`frontend/src/features/billing/types.ts`

```typescript
export const PLAN_CODES = ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'] as const;
export type PlanCode = (typeof PLAN_CODES)[number];

export const PLAN_CODE_ORDER: readonly PlanCode[] = [
  'FREE',
  'PRO_MONTHLY',
  'PRO_YEARLY',
];

export function isPlanCode(value: unknown): value is PlanCode;
export function toPlanCodeOrFree(value: unknown): PlanCode;
export function isProPlanCode(code: PlanCode): boolean;
```

**Результат**
- Один файл = вся правда о тарифах
- Типы, порядок, guards и fallback-логика больше не размазаны по проекту

---

### 2. Deprecated Legacy Type

В `types/billing.ts` сохранена обратная совместимость:

```typescript
import type { PlanCode } from '../features/billing/types';

/** @deprecated Use PlanCode from 'features/billing/types' */
export type BillingPlanCode = PlanCode;
```

**Результат**
- Старые импорты не ломаются
- Чёткий сигнал для будущей чистки

---

### 3. Removed Duplicates

| File | Removed |
|------|---------|
| `planCardState.tsx` | локальный `PLAN_CODES`, `isPlanCode` |
| `useSubscriptionPlans.ts` | `ORDER` массив, локальная валидация |
| `utils/types.ts` | **файл удалён** (мигрирован в SSOT) |

**Результат**
- Нет расхождений между UI, хуками и utils
- Невозможно "забыть" обновить одно из мест

---

### 4. Validation Cleanup

В `validation.ts`:

- `assertBillingPlanCode` → deprecated alias для `isPlanCode`
- `validatePlanCode` → использует `toPlanCodeOrFree`
- `isPlanCodePro` → deprecated re-export `isProPlanCode`

**DEV / PROD поведение:**
- **DEV**: `console.error`, без blocking `alert`
- **PROD**: `console.warn` + fallback в `FREE`

**Результат**
- Один путь валидации
- Fail-safe поведение без UX-побочных эффектов

---

### 5. Public / Internal API Split

Введено разделение экспортов:

| File | Purpose |
|------|---------|
| `billing/index.ts` | публичный API (pages, hooks, SSOT types/utils) |
| `billing/internal.ts` | внутренние реализации (PlanCard, buildPlanCardState) |

**Результат**
- Внешние модули не зависят от внутренней структуры billing
- Billing можно рефакторить без каскадных изменений

---

### 6. Interface Documentation

В `planCardState.tsx` добавлена явная документация SSOT:

- `billing.subscription` → статус, активность, автопродление, платёжный метод
- `billingMe.plan_code` → точный план (MONTHLY / YEARLY), если backend его отдал

**Standalone `subscription` параметр:**
- помечен как `@deprecated`
- оставлен временно, для безопасной миграции

---

## Verification

| Check | Status |
|-------|--------|
| TypeScript compiles | ✅ Passed (1819 modules) |
| Duplicate plan code arrays | ✅ None found |
| No deep imports outside billing | ✅ Verified |
| Subscription page renders correctly | ✅ Verified |

---

## Future Work (Intentionally Deferred)

1. **Удалить deprecated `subscription` параметр**  
   → после обновления `SubscriptionPage` call-site

2. **Удалить deprecated exports**  
   → после подтверждения отсутствия внешних зависимостей

Оба шага не срочные и требуют отдельного PR.

---

## Итог

Billing теперь:
- имеет жёсткий SSOT
- защищён от расхождений типов
- читается как доменная система, а не набор файлов
- готов к дальнейшему расширению (trial, grace, pause) без переписывания

**Это корректная точка, чтобы зафиксировать модуль и двигаться дальше.**
