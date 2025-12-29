/**
 * Mock subscription plans for development/testing
 * Matches SubscriptionPlan interface from types/billing.ts
 */

import type { SubscriptionPlan } from '../../../types/billing';

export const mockSubscriptionPlans: SubscriptionPlan[] = [
    {
        code: 'FREE',
        display_name: 'Базовый',
        price: 0,
        duration_days: 0,
        daily_photo_limit: 3,
        history_days: 7,
        ai_recognition: true,
        advanced_stats: false,
        priority_support: false,
        features: [
            '3 анализа по фото в день',
            'Базовый расчет КБЖУ',
            'История за 7 дней',
            'Ручной ввод безлимитно'
        ],
        is_popular: false,
    },
    {
        code: 'PRO_MONTHLY',
        display_name: 'PRO Месяц',
        price: 299,
        duration_days: 30,
        daily_photo_limit: null, // unlimited
        history_days: -1, // unlimited
        ai_recognition: true,
        advanced_stats: true,
        priority_support: true,
        features: [
            'Безлимит анализов по фото',
            'Приоритетная обработка AI',
            'Расширенная аналитика и тренды',
            'Полная история приемов пищи',
            'Персональные рекомендации'
        ],
        is_popular: true,
        old_price: 499,
    },
    {
        code: 'PRO_YEARLY',
        display_name: 'PRO Год',
        price: 2990,
        duration_days: 365,
        daily_photo_limit: null, // unlimited
        history_days: -1, // unlimited
        ai_recognition: true,
        advanced_stats: true,
        priority_support: true,
        features: [
            'Все преимущества PRO',
            'Выгода более 15%',
            'Безлимитный AI анализ',
            'Приоритетная поддержка',
            'Экспорт отчетов (скоро)'
        ],
        is_popular: false,
        old_price: 4990,
    }
];
