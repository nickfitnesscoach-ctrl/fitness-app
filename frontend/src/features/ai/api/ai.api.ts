/**
 * AI Recognition API
 * 
 * Implements endpoints from API Contract:
 * - POST /api/v1/ai/recognize/
 * - GET /api/v1/ai/task/<id>/
 */

import {
    fetchWithTimeout,
    getHeaders,
    getHeadersWithoutContentType,
    log,
    throwApiError,
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
 * Recognize food from image (async mode)
 * POST /api/v1/ai/recognize/
 * 
 * @param imageFile - Image file (JPEG/PNG)
 * @param userComment - Optional user comment about the food
 * @param mealType - Meal type (breakfast/lunch/dinner/snack)
 * @param date - Date string YYYY-MM-DD
 * @returns RecognizeResponse with task_id for polling
 */
export const recognizeFood = async (
    imageFile: File,
    userComment?: string,
    mealType?: MealType | string,
    date?: string
): Promise<RecognizeResponse> => {
    log(`AI recognize: ${imageFile.name}`);

    const formData = new FormData();
    formData.append('image', imageFile);

    // API uses user_comment (not description)
    if (userComment) {
        formData.append('user_comment', userComment);
    }

    // API uses lowercase meal_type
    if (mealType) {
        formData.append('meal_type', mealType.toLowerCase());
    }

    if (date) {
        formData.append('date', date);
    }

    const response = await fetchWithTimeout(URLS.recognize, {
        method: 'POST',
        headers: getHeadersWithoutContentType(),
        body: formData,
    });

    // Log X-Request-ID for debugging
    const requestId = response.headers.get('X-Request-ID');
    if (requestId) {
        log(`X-Request-ID: ${requestId}`);
    }

    // Handle 429 (daily limit) - per contract: {detail: "Request was throttled..."}
    if (response.status === 429) {
        const data = await response.json().catch(() => ({}));
        const error = new Error(data.detail || 'Дневной лимит исчерпан');
        (error as any).code = 'DAILY_LIMIT_REACHED';
        (error as any).error = 'DAILY_LIMIT_REACHED';
        throw error;
    }

    // Handle other errors
    if (!response.ok && response.status !== 202) {
        await throwApiError(response, 'Ошибка распознавания');
    }

    // 202 Accepted = async processing started
    const data = await response.json();
    log(`Async mode: task_id=${data.task_id}, meal_id=${data.meal_id}`);

    return {
        task_id: data.task_id,
        meal_id: data.meal_id,
        status: 'processing',
    };
};

// ============================================================
// Task Status (for async recognition)
// ============================================================

/**
 * Get task status
 * GET /api/v1/ai/task/<task_id>/
 */
export const getTaskStatus = async (taskId: string): Promise<TaskStatusResponse> => {
    log(`Get task status: ${taskId}`);

    const response = await fetchWithTimeout(URLS.taskStatus(taskId), {
        method: 'GET',
        headers: getHeaders(),
    });

    if (!response.ok) {
        await throwApiError(response, 'Ошибка получения статуса задачи');
    }

    const data = await response.json();
    log(`Task ${taskId}: state=${data.state}, status=${data.status}`);

    return {
        task_id: data.task_id,
        status: data.status,
        state: data.state,
        result: data.result,
        error: data.error,
    };
};

// ============================================================
// Mapping Helpers
// ============================================================

/**
 * Map API result to UI display format
 * Converts API's amount_grams → UI's grams
 * Converts API's items → UI's recognized_items
 */
export const mapToAnalysisResult = (
    result: TaskStatusResponse['result'],
    mealId?: number | string,
    photoUrl?: string
): AnalysisResult | null => {
    if (!result) return null;

    const recognizedItems: RecognizedItem[] = result.items.map((item, index) => ({
        id: String(index),
        name: item.name,
        grams: item.amount_grams, // API → UI mapping
        calories: item.calories,
        protein: item.protein,
        fat: item.fat,
        carbohydrates: item.carbohydrates,
    }));

    return {
        meal_id: mealId ?? result.meal_id,
        recognized_items: recognizedItems,
        total_calories: result.totals?.calories ?? 0,
        total_protein: result.totals?.protein ?? 0,
        total_fat: result.totals?.fat ?? 0,
        total_carbohydrates: result.totals?.carbohydrates ?? 0,
        photo_url: photoUrl,
    };
};
