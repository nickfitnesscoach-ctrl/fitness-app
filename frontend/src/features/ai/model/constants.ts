/**
 * AI Feature Constants
 * 
 * Aligned with API Contract polling recommendations
 */

// ============================================================
// Polling Configuration (per API Contract)
// ============================================================

/**
 * Polling config for task status
 * Contract recommends: 1-2 seconds interval, 60s client timeout
 */
export const POLLING_CONFIG = {
    /** Initial delay between polls (ms) */
    INITIAL_DELAY_MS: 1500,
    /** Maximum delay between polls (ms) */
    MAX_DELAY_MS: 5000,
    /** Backoff multiplier for exponential backoff */
    BACKOFF_MULTIPLIER: 1.5,
    /** Maximum client-side polling duration (ms) */
    CLIENT_TIMEOUT_MS: 60000,
    /** Server-side Celery timeout (for reference) */
    SERVER_TIMEOUT_MS: 90000,
} as const;

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
} as const;

export type AiErrorCode = typeof AI_ERROR_CODES[keyof typeof AI_ERROR_CODES];

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
    /** Maximum file size in MB */
    MAX_PHOTO_SIZE_MB: 10,
    /** Maximum file size in bytes */
    MAX_PHOTO_SIZE_BYTES: 10 * 1024 * 1024,
} as const;
