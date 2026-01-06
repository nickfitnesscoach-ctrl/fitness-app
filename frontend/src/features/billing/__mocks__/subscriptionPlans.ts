/**
 * DEV-only mock data for subscription plans.
 * 
 * RULES:
 * 1. Only imported in useSubscriptionPlans.ts
 * 2. Matches API response 1:1 (SubscriptionPlan interface)
 * 3. Stress-tests UI: long texts, edge cases, 0₽
 * 
 * @see src/types/billing.ts for SubscriptionPlan interface
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
            '3 AI-распознавания в день',
            'Базовый расчет КБЖУ',
            'История питания (7 дней)',
        ],
    },
    {
        code: 'PRO_MONTHLY',
        display_name: 'PRO Месяц',
        price: 299,
        duration_days: 30,
        daily_photo_limit: null,
        history_days: -1,
        ai_recognition: true,
        advanced_stats: true,
        priority_support: true,
        features: [
            'Полная свобода питания',
            'Мгновенный подсчет калорий',
            'Анализ прогресса и привычек',
            'Адаптивный план под твою цель',
        ],
    },
    {
        code: 'PRO_YEARLY',
        display_name: 'PRO Год',
        price: 2990,
        duration_days: 365,
        daily_photo_limit: null,
        history_days: -1,
        ai_recognition: true,
        advanced_stats: true,
        priority_support: true,
        is_popular: true,
        old_price: 4990,
        features: [
            'Все функции PRO-доступа',
            'Бонус: Стратегия с тренером',
            'Аудит твоего питания',
            'План выхода на цель',
        ],
    },
];
