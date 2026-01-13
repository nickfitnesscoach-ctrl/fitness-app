/**
 * Validation utilities for billing module
 *
 * NOTE: Core validation (isPlanCode, toPlanCodeOrFree, isProPlanCode)
 * is now in billing/types.ts (SSOT). This file provides:
 * - Backward-compatible re-exports
 * - validatePlanCode with toast notification (DEV-only)
 */

import { isPlanCode, toPlanCodeOrFree, isProPlanCode, type PlanCode } from '../types';
import { IS_DEV } from '../../../config/env';
import { showToast } from './notify';

// Re-export from SSOT for backward compatibility
export { isPlanCode, isProPlanCode };

/**
 * @deprecated Use isPlanCode from '../types' instead.
 * This is an alias for backward compatibility.
 */
export const assertBillingPlanCode = isPlanCode;

/**
 * Валидируем plan_code с логированием и опциональным тостом в DEV.
 *
 * @deprecated Prefer toPlanCodeOrFree from '../types' for simpler use cases.
 * Use this function only if you need the DEV toast notification.
 */
export function validatePlanCode(planCode: unknown): PlanCode {
    if (isPlanCode(planCode)) {
        return planCode;
    }

    const message = `Unknown plan_code received: ${String(planCode)}`;

    if (IS_DEV) {
        // eslint-disable-next-line no-console
        console.error(`[Billing] ${message}`);

        // DEV: show toast for visibility (no blocking alert)
        try {
            showToast(`DEV: ${message}`);
        } catch {
            // ignore if toast is unavailable
        }
    } else {
        // eslint-disable-next-line no-console
        console.warn(`[Billing] ${message}, falling back to FREE`);
    }

    return toPlanCodeOrFree(planCode);
}

/**
 * @deprecated Use isPlanCodePro from '../types' instead.
 * This is a re-export for backward compatibility.
 */
export function isPlanCodePro(planCode: PlanCode): boolean {
    return isProPlanCode(planCode);
}
