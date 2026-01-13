/**
 * Billing Types - Single Source of Truth (SSOT)
 *
 * This file is the CANONICAL source for all plan code definitions.
 * All billing-related type guards, constants, and helpers live here.
 *
 * @module billing/types
 */

// ============================================================================
// PLAN CODES - SSOT
// ============================================================================

/**
 * All valid plan codes as a const tuple.
 * This is the single source of truth for plan code values.
 */
export const PLAN_CODES = ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'] as const;

/**
 * Union type of all valid plan codes, derived from PLAN_CODES.
 */
export type PlanCode = (typeof PLAN_CODES)[number];

/**
 * Explicit UI ordering for plan cards.
 * Controls how plans are displayed in the subscription page.
 */
export const PLAN_CODE_ORDER: readonly PlanCode[] = ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'] as const;

// ============================================================================
// TYPE GUARDS & VALIDATORS
// ============================================================================

/**
 * Type guard: checks if a value is a valid PlanCode.
 *
 * Use this when receiving data from API or localStorage.
 *
 * @example
 * const code = response.plan_code;
 * if (isPlanCode(code)) {
 *   // code is PlanCode here
 * }
 */
export function isPlanCode(value: unknown): value is PlanCode {
    return typeof value === 'string' && (PLAN_CODES as readonly string[]).includes(value);
}

/**
 * Safe conversion: unknown value → PlanCode, with 'FREE' as fallback.
 *
 * Behavior:
 * - DEV: logs console.error for unknown values
 * - PROD: logs console.warn and silently falls back
 *
 * @example
 * const planCode = toPlanCodeOrFree(apiResponse.plan_code);
 * // planCode is always a valid PlanCode
 */
export function toPlanCodeOrFree(value: unknown): PlanCode {
    if (isPlanCode(value)) {
        return value;
    }

    const message = `[Billing] Unknown plan_code: ${String(value)}, falling back to FREE`;

    if (import.meta.env.DEV) {
        // eslint-disable-next-line no-console
        console.error(message);
    } else {
        // eslint-disable-next-line no-console
        console.warn(message);
    }

    return 'FREE';
}

// ============================================================================
// HELPERS
// ============================================================================

/**
 * Check if a plan code represents a PRO subscription.
 */
export function isProPlanCode(code: PlanCode): boolean {
    return code === 'PRO_MONTHLY' || code === 'PRO_YEARLY';
}
