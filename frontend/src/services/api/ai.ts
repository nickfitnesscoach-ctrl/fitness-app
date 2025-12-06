/**
 * AI Recognition API Module
 * 
 * Handles food photo recognition with sync/async modes.
 */

import {
    fetchWithTimeout,
    getHeaders,
    getHeadersWithoutContentType,
    log,
    API_BASE
} from './client';
import { URLS } from './urls';

// ============================================================
// AI Recognition
// ============================================================

export interface RecognizeResult {
    recognized_items: Array<{
        name: string;
        grams: number;
        calories: number;
        protein: number;
        fat: number;
        carbohydrates: number;
    }>;
    total_calories: number;
    total_protein: number;
    total_fat: number;
    total_carbohydrates: number;
    meal_id?: number | string;
    photo_url?: string;
    isAsync: false;
}

export interface RecognizeAsyncResult {
    task_id: string;
    meal_id: string;
    status: string;
    message?: string;
    isAsync: true;
}

export type RecognizeFoodResult = RecognizeResult | RecognizeAsyncResult;

/**
 * Recognize food from image
 * Supports both sync (HTTP 200) and async (HTTP 202) backend modes
 */
export const recognizeFood = async (
    imageFile: File,
    description?: string,
    mealType?: string,
    date?: string
): Promise<RecognizeFoodResult> => {
    log(`Calling AI recognize endpoint with file: ${imageFile.name}`);

    try {
        const formData = new FormData();
        formData.append('image', imageFile);
        if (description) {
            formData.append('description', description);
        }
        if (mealType) {
            formData.append('meal_type', mealType);
        }
        if (date) {
            formData.append('date', date);
        }

        const headers = getHeadersWithoutContentType();

        const response = await fetchWithTimeout(URLS.recognize, {
            method: 'POST',
            headers: headers,
            body: formData,
        });

        // Handle async mode (HTTP 202 Accepted)
        if (response.status === 202) {
            const asyncResult = await response.json();
            console.log('RECOGNIZE ASYNC MODE', response.status, asyncResult);
            log(`AI recognition async: task_id=${asyncResult.task_id}, meal_id=${asyncResult.meal_id}`);

            return {
                task_id: asyncResult.task_id,
                meal_id: asyncResult.meal_id,
                status: asyncResult.status || 'processing',
                isAsync: true,
                message: asyncResult.message
            };
        }

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.log('RECOGNIZE ERROR RESPONSE', response.status, errorData);
            log(`AI recognition error: ${errorData.error || errorData.detail || response.status}`);

            const error = new Error(errorData.detail || errorData.error || `AI recognition failed(${response.status})`);
            (error as any).error = errorData.error || 'UNKNOWN_ERROR';
            (error as any).detail = errorData.detail || error.message;
            (error as any).status = response.status;
            (error as any).data = errorData;
            throw error;
        }

        // Sync mode (HTTP 200)
        const backendResult = await response.json();
        console.log('RECOGNIZE OK', response.status, backendResult);
        log(`RAW AI response: ${JSON.stringify(backendResult)}`);

        const mappedResult: RecognizeResult = {
            recognized_items: backendResult.recognized_items || [],
            total_calories: backendResult.total_calories || 0,
            total_protein: backendResult.total_protein || 0,
            total_fat: backendResult.total_fat || 0,
            total_carbohydrates: backendResult.total_carbohydrates || 0,
            meal_id: backendResult.meal_id,
            photo_url: backendResult.photo_url,
            isAsync: false
        };

        log(`AI recognized ${mappedResult.recognized_items.length} items`);
        console.log('MAPPED RESULT', mappedResult);
        return mappedResult;
    } catch (error: unknown) {
        const err = error as Error & { message?: string; status?: number; data?: unknown };
        console.log('RECOGNIZE ERROR CATCH', err?.message, err?.status, err?.data);
        console.error('AI recognition error:', error);
        throw error;
    }
};

// ============================================================
// Task Status (for async recognition)
// ============================================================

export interface TaskTotals {
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

export interface TaskResult {
    success: boolean;
    meal_id: string | number;
    recognized_items: Array<{
        id: string;
        name: string;
        grams: number;
        calories: number;
        protein: number;
        fat: number;
        carbohydrates: number;
        confidence?: number;
    }>;
    totals: TaskTotals;
    recognition_time?: number;
    photo_url?: string;
    error?: string;
}

export interface TaskStatusResponse {
    task_id: string;
    state: 'PENDING' | 'STARTED' | 'RETRY' | 'SUCCESS' | 'FAILURE';
    result?: TaskResult;
    error?: string;
    message?: string;
}

export const getTaskStatus = async (taskId: string): Promise<TaskStatusResponse> => {
    log(`Getting task status: ${taskId}`);
    try {
        const response = await fetchWithTimeout(`${API_BASE}/ai/task/${taskId}/`, {
            method: 'GET',
            headers: getHeaders(),
        });

        if (!response.ok) {
            throw new Error(`Failed to get task status: ${response.status}`);
        }

        const data = await response.json();
        log(`Task ${taskId} status: ${data.state}`);
        return data;
    } catch (error) {
        console.error('Error getting task status:', error);
        throw error;
    }
};
