/**
 * Billing Feature Module
 * 
 * Isolated domain for subscription, payment, and billing UI.
 * All billing-related components, hooks, and utilities are exported from here.
 */

// Pages
export { default as SubscriptionPage } from './pages/SubscriptionPage';
export { default as SubscriptionDetailsPage } from './pages/SubscriptionDetailsPage';
export { default as PaymentHistoryPage } from './pages/PaymentHistoryPage';

// Components
export { default as PlanCard } from './components/PlanCard';
export type { Plan, PlanId } from './components/PlanCard';
export { SubscriptionHeader } from './components/subscription/SubscriptionHeader';
export { default as AdminTestPaymentCard } from './components/billing/AdminTestPaymentCard';
export { default as PaymentHistoryList } from './components/billing/PaymentHistoryList';

// Hooks
export { useSubscriptionPlans } from './hooks/useSubscriptionPlans';
export { useSubscriptionStatus } from './hooks/useSubscriptionStatus';
export { useSubscriptionActions } from './hooks/useSubscriptionActions';
export { useSubscriptionDetails } from './hooks/useSubscriptionDetails';
export { usePaymentHistory } from './hooks/usePaymentHistory';
export { usePaymentPolling, setPollingFlagForPayment, clearPollingFlag } from './hooks/usePaymentPolling';

// Utils
export { formatBillingDate, formatShortDate, formatDate } from './utils/date';
export { showToast, showSuccess, showError } from './utils/notify';
export { assertBillingPlanCode, validatePlanCode, isPlanCodePro } from './utils/validation';
export { buildPlanCardState } from './utils/planCardState';

// Mocks (for development)
export { mockSubscriptionPlans } from './__mocks__/plans';
