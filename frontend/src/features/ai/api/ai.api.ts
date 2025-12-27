import {
    fetchWithTimeout,
    getHeadersWithoutContentType,
    log,
} from '../../../services/api/client';
import { URLS } from '../../../services/api/urls';
import type {
    RecognizeResponse,
    TaskStatusResponse,
    AnalysisResult,
    RecognizedItem,
    MealType,
} from './ai.types';

// ============================================================
// AI Recognition
// ============================================================

/**
 * Map UI meal type to API meal type
 * UI uses lowercase (завтрак → breakfast)
 * API uses UPPERCASE (BREAKFAST, LUNCH, DINNER, SNACK)
 */
const MEAL_TYPE_MAP: Record<string, string> = {
    'завтрак': 'BREAKFAST',
    'breakfast': 'BREAKFAST',
    'обед': 'LUNCH',
    'lunch': 'LUNCH',
    'ужин': 'DINNER',
    'dinner': 'DINNER',
    'перекус': 'SNACK',
    'snack': 'SNACK',
};

/**
 * Convert UI meal type to API format
 * @param mealType - Meal type from UI (e.g., "Завтрак", "breakfast", "BREAKFAST")
 * @returns API-compatible meal type (BREAKFAST/LUNCH/DINNER/SNACK) or undefined
 */
const mapMealTypeToApi = (mealType?: string): string | undefined => {
    if (!mealType) return undefined;

    // Normalize to lowercase for lookup
    const normalized = mealType.toLowerCase().trim();

    // Return mapped value or fallback to SNACK if unknown
    return MEAL_TYPE_MAP[normalized] || 'SNACK';
};

/**
 * Recognize food from image (async mode)
 * POST /api/v1/ai/recognize/
 *
 * @param imageFile - Image file (JPEG/PNG)
 * @param userComment - Optional user comment about the food
 * @param mealType - Meal type (breakfast/lunch/dinner/snack)
 * @param date - Date string YYYY-MM-DD
 * @param signal - Optional AbortSignal for cancellation
 * @returns RecognizeResponse with task_id for polling
 */
export const recognizeFood = async (
    imageFile: File,
    userComment?: string,
    mealType?: MealType | string,
    date?: string,
    signal?: AbortSignal
): Promise<RecognizeResponse> => {
    log(`AI recognize: ${imageFile.name}`);

    const formData = new FormData();
    formData.append('image', imageFile);

    // API uses user_comment (not description)
    if (userComment) {
        formData.append('user_comment', userComment);
    }

    // Map UI meal type to API format (UPPERCASE)
    const apiMealType = mapMealTypeToApi(mealType);
    if (apiMealType) {
        formData.append('meal_type', apiMealType);
    }

    if (date) {
        formData.append('date', date);
    }

    const response = await fetchWithTimeout(
        URLS.recognize,
        {
            method: 'POST',
            headers: getHeadersWithoutContentType(),
            body: formData,
        },
        undefined, // default timeout
        false,     // skipAuthCheck
        signal     // external abort signal
    );

    // Log X-Request-ID for debugging
    const requestId = response.headers.get('X-Request-ID');
    if (requestId) {
        log(`X-Request-ID: ${requestId}`);
    }

    // Handle 429 (daily limit) - per contract: {error: "...", message: "...", used: ..., limit: ...}
    if (response.status === 429) {
        const data = await safeJsonParse(response);

        // P0-1: Throw specific Error for daily limit
        if (data.error === 'DAILY_PHOTO_LIMIT_EXCEEDED') {
            const error = new Error(data.message || 'Дневной лимит фото исчерпан');
            (error as any).code = 'DAILY_LIMIT_REACHED';
            (error as any).error = 'DAILY_LIMIT_REACHED';
            (error as any).data = data;
            throw error;
        }

        // Fallback for other throttles
        const error = new Error(data.detail || data.message || 'Слишком много запросов. Попробуйте позже.');
        (error as any).code = 'THROTTLED';
        throw error;
    }

    if (response.status !== 202) {
        const data = await safeJsonParse(response);
        throw new Error(data.message || 'Ошибка запуска распознавания');
    }

    return await safeJsonParse(response);
};

// ============================================================
// Task Status (for async recognition)
// ============================================================

/**
 * Get task status
 * GET /api/v1/ai/task/<task_id>/
 * @param signal - Optional AbortSignal for cancellation
 */
export const getTaskStatus = async (
    taskId: string,
    signal?: AbortSignal
): Promise<TaskStatusResponse> => {
    log(`Get task status: ${taskId}`);

    const response = await fetch(`${URLS.taskStatus(taskId)}`, { // Changed URLS.taskStatus(taskId) to template literal
        method: 'GET',
        headers: {
            ...getAuthHeaders(),
            'Content-Type': 'application/json',
        },
        signal,
    });

    if (response.status === 404) {
        throw new Error('Задача не найдена или доступ запрещен');
    }

    if (!response.ok) {
        const data = await safeJsonParse(response);
        throw new Error(data.message || 'Ошибка при получении статуса');
    }

    return await safeJsonParse(response);
};

const getAuthHeaders = () => {
    const initData = (window as any).Telegram?.WebApp?.initData || '';
    return {
        'Authorization': `Bearer ${initData}`,
        'X-Telegram-Init-Data': initData,
    };
};

/**
 * P0-Contract: Robust JSON parsing
 */
const safeJsonParse = async (response: Response) => {
    try {
        return await response.json();
    } catch (e) {
        console.error('[AI API] JSON parse error:', e);
        return {};
    }
};

// ============================================================
// Mapping Helpers
// ============================================================

/**
 * P0 Data Integrity & API Contract:
 * - return null if !result OR result.error OR !items OR items.length==0
 * - generate stable item ids
 */
export const mapToAnalysisResult = (taskStatus: TaskStatusResponse): AnalysisResult | null => {
    const result = taskStatus.result;

    // P0-Contract Check: Fail if there's a result-level error or no items
    if (!result || result.error || !result.items || result.items.length === 0) {
        return null;
    }

    // Success - map items to UI format (amount_grams -> grams)
    const items: RecognizedItem[] = result.items.map((apiItem) => ({
        id: crypto.randomUUID(), // P0: Stable unique ID
        name: apiItem.name,
        grams: apiItem.amount_grams,
        calories: apiItem.calories,
        protein: apiItem.protein,
        fat: apiItem.fat,
        carbohydrates: apiItem.carbohydrates,
    }));

    return {
        meal_id: result.meal_id,
        recognized_items: items,
        total_calories: result.totals.calories,
        total_protein: result.totals.protein,
        total_fat: result.totals.fat,
        total_carbohydrates: result.totals.carbohydrates,
    };
};
