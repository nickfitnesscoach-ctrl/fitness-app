/**
 * Frontend SSOT for plan marketing copy.
 *
 * ВАЖНО:
 * - Billing truth (price, duration_days, old_price) comes from API
 * - Marketing copy (displayName, features, badge, order) lives here
 *
 * Если нужно поменять тексты на карточках — правь ТОЛЬКО этот файл.
 * Если нужно поменять цену/скидку — правь Django Admin.
 *
 * @module billing/config/planCopy
 */

export interface PlanCopyConfig {
    /** Название для отображения в UI */
    displayName: string;
    /** Бейдж (например "ВЫБОР ПОЛЬЗОВАТЕЛЕЙ"), опционально */
    badge?: string;
    /** Список ценностей/фич для карточки */
    features: string[];
    /** Якорная цена (fallback, если API вернул null) */
    oldPrice?: number;
    /** Порядок отображения (меньше = выше) */
    order: number;
}

/**
 * Marketing copy for known plan codes.
 *
 * Порядок: PRO Год (1) → PRO Месяц (2) → Базовый (3)
 */
export const PLAN_COPY: Record<string, PlanCopyConfig> = {
    PRO_YEARLY: {
        displayName: 'PRO Год',
        badge: 'ВЫБОР ПОЛЬЗОВАТЕЛЕЙ',
        features: [
            'Все функции PRO-доступа',
            '60-мин стратегия с тренером (5000₽)',
            'Аудит твоего питания',
            'План выхода на цель',
        ],
        oldPrice: 4990,  // Fallback if DB not yet populated
        order: 1,
    },
    PRO_MONTHLY: {
        displayName: 'PRO Месяц',
        features: [
            'Полная свобода питания',
            'Мгновенный подсчет калорий',
            'Анализ прогресса и привычек',
            'Адаптивный план под твою цель',
        ],
        order: 2,
    },
    FREE: {
        displayName: 'Базовый',
        features: [
            '3 AI-распознавания в день',
            'Базовый расчет КБЖУ',
            'История питания (7 дней)',
        ],
        order: 3,
    },
};

/**
 * Get plan copy with safe fallback for unknown codes.
 *
 * @param code - plan.code from API
 * @returns PlanCopyConfig (guaranteed, never undefined)
 */
export function getPlanCopy(code: string): PlanCopyConfig {
    const copy = code in PLAN_COPY ? PLAN_COPY[code] : null;

    if (copy) {
        // Defensive: ensure features is always an array
        return {
            ...copy,
            features: Array.isArray(copy.features) ? copy.features : [],
        };
    }

    // Fallback for unknown plan codes: show code as displayName, no features
    if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.warn(`[Billing] Unknown plan code "${code}", using fallback copy`);
    }

    return {
        displayName: code,
        features: [],
        order: 999,
    };
}
