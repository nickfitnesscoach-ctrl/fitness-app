/**
 * AI Feature Constants
 * 
 * Aligned with API Contract polling recommendations
 */

import type { PhotoUploadStatus } from './types';

// ============================================================
// Polling Configuration (2-phase strategy)
// ============================================================

/**
 * Polling config for task status
 * Phase 1 (fast): 1s interval for first 15 seconds
 * Phase 2 (slow): 3s interval after 15 seconds
 */
export const POLLING_CONFIG = {
    /** Duration of fast polling phase (ms) */
    FAST_PHASE_DURATION_MS: 15000,
    /** Delay between polls in fast phase (ms) */
    FAST_PHASE_DELAY_MS: 1000,
    /** Delay between polls in slow phase (ms) */
    SLOW_PHASE_DELAY_MS: 3000,
    /** Maximum delay in slow phase with backoff (ms) */
    SLOW_PHASE_MAX_DELAY_MS: 5000,
    /** Backoff multiplier for slow phase */
    BACKOFF_MULTIPLIER: 1.3,
    /** Maximum client-side polling duration (ms) */
    CLIENT_TIMEOUT_MS: 60000,
    /** Server-side Celery timeout (for reference) */
    SERVER_TIMEOUT_MS: 90000,
} as const;

// ============================================================
// Photo Status Labels (Russian)
// ============================================================

export const PHOTO_STATUS_LABELS: Record<PhotoUploadStatus, string> = {
    pending: 'Ожидает…',
    compressing: 'Сжимаю фото…',
    uploading: 'Загружаю…',
    processing: 'В обработке…',
    success: 'Готово ✅',
    error: 'Ошибка',
};

// ============================================================
// Meal Types (lowercase per API Contract)
// ============================================================

export const MEAL_TYPES = {
    BREAKFAST: 'breakfast',
    LUNCH: 'lunch',
    DINNER: 'dinner',
    SNACK: 'snack',
} as const;

export const MEAL_TYPE_OPTIONS = [
    { value: 'breakfast', label: 'Завтрак' },
    { value: 'lunch', label: 'Обед' },
    { value: 'dinner', label: 'Ужин' },
    { value: 'snack', label: 'Перекус' },
] as const;

// ============================================================
// AI Error Codes
// ============================================================

export const AI_ERROR_CODES = {
    DAILY_LIMIT_REACHED: 'DAILY_LIMIT_REACHED',
    RECOGNITION_FAILED: 'RECOGNITION_FAILED',
    TASK_TIMEOUT: 'TASK_TIMEOUT',
    TASK_FAILURE: 'TASK_FAILURE',
    NETWORK_ERROR: 'NETWORK_ERROR',
    EMPTY_RESULT: 'EMPTY_RESULT',
    CANCELLED: 'CANCELLED',
    // Preprocess errors
    PREPROCESS_DECODE_FAILED: 'PREPROCESS_DECODE_FAILED',
    PREPROCESS_TIMEOUT: 'PREPROCESS_TIMEOUT',
    PREPROCESS_INVALID_IMAGE: 'PREPROCESS_INVALID_IMAGE',
} as const;

export type AiErrorCode = typeof AI_ERROR_CODES[keyof typeof AI_ERROR_CODES];

/**
 * Error codes that should NOT allow retry
 * (e.g., daily limit - user must wait or upgrade)
 */
export const NON_RETRYABLE_ERROR_CODES = new Set<string>([
    AI_ERROR_CODES.DAILY_LIMIT_REACHED,
]);

// ============================================================
// AI Error Messages (Russian)
// ============================================================

export const AI_ERROR_MESSAGES: Record<string, string> = {
    [AI_ERROR_CODES.DAILY_LIMIT_REACHED]: 'Дневной лимит исчерпан. Оформите PRO для безлимита.',
    [AI_ERROR_CODES.RECOGNITION_FAILED]: 'Не удалось распознать еду на фото',
    [AI_ERROR_CODES.TASK_TIMEOUT]: 'Превышено время ожидания. Попробуйте ещё раз.',
    [AI_ERROR_CODES.TASK_FAILURE]: 'Ошибка обработки фото',
    [AI_ERROR_CODES.NETWORK_ERROR]: 'Ошибка сети. Проверьте интернет-соединение.',
    [AI_ERROR_CODES.EMPTY_RESULT]: 'Мы не смогли распознать еду на фото. Попробуйте сделать фото крупнее.',
    // Preprocess errors
    [AI_ERROR_CODES.PREPROCESS_DECODE_FAILED]: 'Не удалось обработать фото. Попробуйте другое или сделайте скриншот.',
    [AI_ERROR_CODES.PREPROCESS_TIMEOUT]: 'Фото слишком тяжёлое. Попробуйте другое или сделайте скриншот.',
    [AI_ERROR_CODES.PREPROCESS_INVALID_IMAGE]: 'Выбранный файл не является изображением.',
    [AI_ERROR_CODES.CANCELLED]: 'Отменено',
    // Backend throttling message pattern
    'Request was throttled': 'Дневной лимит исчерпан. Оформите PRO для безлимита.',
};

/**
 * Get localized error message
 */
export function getAiErrorMessage(errorCode: string | undefined, fallback?: string): string {
    if (!errorCode) {
        return fallback || 'Произошла ошибка. Попробуйте ещё раз.';
    }

    // Exact match
    if (AI_ERROR_MESSAGES[errorCode]) {
        return AI_ERROR_MESSAGES[errorCode];
    }

    // Partial match (for backend messages like "Request was throttled...")
    const lowerCode = errorCode.toLowerCase();
    for (const [key, message] of Object.entries(AI_ERROR_MESSAGES)) {
        if (lowerCode.includes(key.toLowerCase())) {
            return message;
        }
    }

    return fallback || errorCode || 'Произошла ошибка. Попробуйте ещё раз.';
}

// ============================================================
// Validation Limits
// ============================================================

export const AI_LIMITS = {
    /** Maximum photos per single upload batch */
    MAX_PHOTOS_PER_UPLOAD: 5,
    // Note: MAX_PHOTO_SIZE_* removed - preprocessing handles size reduction automatically
} as const;
