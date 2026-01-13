/**
 * Типы для Billing API
 */

import type { PlanCode } from '../features/billing/types';

/**
 * @deprecated Use PlanCode from 'features/billing/types' instead.
 * This alias exists for backward compatibility with existing code.
 */
export type BillingPlanCode = PlanCode;

// Re-export for convenience
export type { PlanCode } from '../features/billing/types';

/**
 * GET /api/v1/billing/me/
 * Основная информация о статусе подписки и лимитах
 */
export interface BillingMe {
    plan_code: BillingPlanCode;
    plan_name: string;
    expires_at: string | null;
    is_active: boolean;
    daily_photo_limit: number | null;   // null = безлимит
    used_today: number;                 // >= 0
    remaining_today: number | null;     // null = безлимит
    test_live_payment_available?: boolean;  // Только для админов в prod режиме
}

export interface BillingState {
    data: BillingMe | null;
    loading: boolean;
    error: string | null;
}

/**
 * GET /api/v1/billing/plans/
 * Публичный список тарифных планов
 */
export interface SubscriptionPlan {
    code: string;
    display_name: string;
    price: number;
    duration_days: number;
    daily_photo_limit: number | null;  // null = безлимит
    history_days: number;              // -1 = безлимит
    ai_recognition: boolean;
    advanced_stats: boolean;
    priority_support: boolean;
    // Frontend-only fields for UI
    features?: string[];
    is_popular?: boolean;
    old_price?: number;
}

export interface CreatePaymentRequest {
    plan_code: string;
    return_url?: string;
    save_payment_method?: boolean;
}

export interface CreatePaymentResponse {
    payment_id: string;
    yookassa_payment_id: string;
    confirmation_url: string;
}

export interface DailyLimitError {
    error: 'DAILY_LIMIT_REACHED';
    detail: string;
    current_plan: BillingPlanCode;
    daily_limit: number;
    used_today: number;
}

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
    card_bound: boolean;  // Explicit flag for card binding status
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
