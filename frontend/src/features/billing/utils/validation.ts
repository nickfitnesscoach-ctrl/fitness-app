/**
 * Validation utilities for billing module (DEV-only extras)
 *
 * NOTE: Core validation (isPlanCode, toPlanCodeOrFree, isProPlanCode)
 * is in billing/types.ts (SSOT).
 *
 * This file provides validatePlanCode with DEV toast notification.
 * For most use cases, prefer toPlanCodeOrFree from '../types'.
 */

import { isPlanCode, toPlanCodeOrFree, type PlanCode } from '../types';
import { IS_DEV } from '../../../config/env';
import { showToast } from './notify';

/**
 * Validate plan_code with logging and DEV toast notification.
 *
 * For simpler use cases without toast, use toPlanCodeOrFree from '../types'.
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
