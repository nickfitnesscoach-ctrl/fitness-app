# Billing SSOT Refactoring — Final

## Summary

Billing-модуль приведён к единому источнику истины (SSOT) по типам и контрактам.  
Удалены все дубли и deprecated exports, публичный API модуля формализован.  
**Поведение продукта не изменено.**

---

## Changes Made

### 1. SSOT Types (`billing/types.ts`)

```typescript
export const PLAN_CODES = ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'] as const;
export type PlanCode = (typeof PLAN_CODES)[number];
export const PLAN_CODE_ORDER: readonly PlanCode[] = [...];

export function isPlanCode(value: unknown): value is PlanCode;
export function toPlanCodeOrFree(value: unknown): PlanCode;
export function isProPlanCode(code: PlanCode): boolean;
```

### 2. Legacy Alias (`types/billing.ts`)

```typescript
/** @deprecated Use PlanCode from 'features/billing/types' */
export type BillingPlanCode = PlanCode;
```

### 3. Removed Duplicates

| File | Removed |
|------|---------|
| `planCardState.tsx` | `PLAN_CODES`, `isPlanCode`, `subscription` param |
| `useSubscriptionPlans.ts` | `ORDER` array, local validation |
| `utils/types.ts` | **deleted** |

### 4. Removed Deprecated Exports

- `assertBillingPlanCode` ❌
- `isPlanCodePro` ❌  
- `validatePlanCode` → оставлен только для DEV toast

### 5. Public / Internal Split

| File | Purpose |
|------|---------|
| `index.ts` | public API |
| `internal.ts` | internal components |

### 6. buildPlanCardState

- `subscription` param removed
- Uses `billing.subscription` only
- SSOT JSDoc added

---

## Verification

| Check | Status |
|-------|--------|
| TypeScript | ✅ 1818 modules |
| No duplicates | ✅ |
| No deprecated exports | ✅ |

---

## API Reference

### Public Exports (`features/billing`)

```typescript
// Types
export type { PlanCode };
export { PLAN_CODES, PLAN_CODE_ORDER, isPlanCode, toPlanCodeOrFree, isProPlanCode };

// Pages
export { SubscriptionPage, SubscriptionDetailsPage, PaymentHistoryPage };

// Hooks
export { useSubscriptionPlans, useSubscriptionStatus, useSubscriptionActions };
export { useSubscriptionDetails, usePaymentHistory, usePaymentPolling };

// Utils
export { formatBillingDate, formatShortDate, formatDate };
export { showToast, showSuccess, showError };
```
