/**
 * DEV-only мок данных для тарифов подписки.
 *
 * Назначение:
 * - используется ТОЛЬКО в DEV-режиме
 * - подменяет реальный API для разработки и тестирования UI
 *
 * ПРАВИЛА ИСПОЛЬЗОВАНИЯ:
 * 1. Импортируется ТОЛЬКО в useSubscriptionPlans.ts
 * 2. Структура данных совпадает с API (SubscriptionPlan)
 * 3. Marketing copy (features, is_popular) moved to PLAN_COPY in planCopy.ts
 * 4. Pricing data (price, old_price, duration_days) stays here (API simulation)
 *
 * ⚠️ ВАЖНО:
 * Этот файл НЕ ДОЛЖЕН попасть в production-сборку.
 *
 * @see src/features/billing/config/planCopy.ts — SSOT для маркетинговых текстов
 */

import type { SubscriptionPlan } from '../../../types/billing';

// Защита от случайного импорта в PROD: не ломаем приложение, но сигналим в консоль.
// В идеале мок не должен попадать в prod-bundle вообще (это обеспечим dynamic import ниже).
if (import.meta.env.PROD) {
    // eslint-disable-next-line no-console
    console.warn('mockSubscriptionPlans was imported in PROD (should not happen)');
}

/**
 * Моки симулируют API ответ: только billing truth.
 * Marketing copy (features) берётся из PLAN_COPY в planCopy.ts.
 */
export const mockSubscriptionPlans: SubscriptionPlan[] = [
    /**
     * FREE — базовый тариф
     */
    {
        code: 'FREE',
        display_name: 'Free',  // DB value, UI uses PLAN_COPY.displayName
        price: 0,
        duration_days: 0,
        daily_photo_limit: 3,
        history_days: 7,
        ai_recognition: true,
        advanced_stats: false,
        priority_support: false,
    },

    /**
     * PRO_MONTHLY — платный тариф на месяц
     */
    {
        code: 'PRO_MONTHLY',
        display_name: 'PRO Monthly',  // DB value
        price: 299,
        duration_days: 30,
        daily_photo_limit: null,
        history_days: -1,
        ai_recognition: true,
        advanced_stats: true,
        priority_support: true,
    },

    /**
     * PRO_YEARLY — годовой тариф (основной продающий)
     */
    {
        code: 'PRO_YEARLY',
        display_name: 'PRO Yearly',  // DB value
        price: 2990,
        old_price: 4990,  // Pricing anchor (editable in Django Admin)
        duration_days: 365,
        daily_photo_limit: null,
        history_days: -1,
        ai_recognition: true,
        advanced_stats: true,
        priority_support: true,
    },
];
