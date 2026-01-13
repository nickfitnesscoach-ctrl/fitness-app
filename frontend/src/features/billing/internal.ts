/**
 * Billing Internal Exports
 *
 * This file exports internal components and utilities that should
 * ONLY be used within the billing module.
 *
 * External code should import from 'features/billing' (index.ts) only.
 */

// ==============================
// Internal: Build helpers
// ==============================
export { buildPlanCardState } from './utils/planCardState';

// ==============================
// Internal: Components
// ==============================
export { default as PlanCard } from './components/PlanCard';
export { BasicPlanCard } from './components/BasicPlanCard';
export { PremiumMonthCard } from './components/PremiumMonthCard';
export { PremiumProCard } from './components/PremiumProCard';
export { SubscriptionHeader } from './components/SubscriptionHeader';
export { default as AdminTestPaymentCard } from './components/AdminTestPaymentCard';
export { default as PaymentHistoryList } from './components/PaymentHistoryList';

// ==============================
// Internal: Types (re-export for convenience)
// ==============================
export type { PlanCode } from './types';
export { PLAN_CODES, PLAN_CODE_ORDER, isPlanCode, toPlanCodeOrFree, isProPlanCode } from './types';
