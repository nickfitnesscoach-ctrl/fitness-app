/**
 * Frontend SSOT for plan marketing copy.
 *
 * ВАЖНО:
 * - Billing truth (price, duration_days, old_price) comes from API (Django).
 * - Marketing copy (displayName, features, badge, order) lives here.
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
    /** Якорная цена (fallback, если API вернул null). В идеале временно. */
    oldPrice?: number;
    /** Порядок отображения (меньше = выше) */
    order: number;
}

/**
 * Marketing copy for known plan codes.
 *
 * Порядок: PRO Год (1) → PRO Месяц (2) → Базовый (3)
 *
 * Примечание:
 * - oldPrice здесь — только fallback на период заполнения БД (old_price).
 *   После заполнения в Django Admin можно удалить.
 */
export const PLAN_COPY = {
    PRO_YEARLY: {
        displayName: 'PRO Год',
        badge: 'ВЫБОР ПОЛЬЗОВАТЕЛЕЙ',
        features: [
            'Все функции PRO-доступа',
            '60-мин стратегия с тренером (5000₽)',
            'Аудит твоего питания',
            'План выхода на цель',
        ],
        oldPrice: 4990, // [TEMP] fallback if DB old_price is null
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
} as const satisfies Record<string, PlanCopyConfig>;

type KnownPlanCode = keyof typeof PLAN_COPY;

/**
 * Get plan copy with safe fallback for unknown codes.
 *
 * @param code - plan.code from API
 * @returns PlanCopyConfig (guaranteed, never undefined)
 */
export function getPlanCopy(code: string): PlanCopyConfig {
    const copy = PLAN_COPY[code as KnownPlanCode];

    if (copy) {
        // Defensive: ensure features is always an array (even if someone edits PLAN_COPY wrong)
        const features = Array.isArray(copy.features) ? copy.features : [];
        return { ...copy, features };
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
