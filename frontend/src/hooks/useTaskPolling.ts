/**
 * Hook for polling AI recognition task status
 * Used when backend returns HTTP 202 (async mode)
 *
 * REFACTORED: Now uses unified api.getTaskStatus() instead of direct fetch
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { ai } from '../services/api';
import type { TaskStatusResponse } from '../services/api/ai';

export type TaskStatus = 'idle' | 'polling' | 'success' | 'failed' | 'timeout';

export interface RecognizedItem {
    name: string;
    grams: number;
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

export interface TaskResult {
    success: boolean;
    meal_id: string;
    recognized_items: RecognizedItem[];
    total_calories?: number;
    total_protein?: number;
    total_fat?: number;
    total_carbohydrates?: number;
    photo_url?: string;
    error?: string;
}

// Helper type for task result totals
type Totals = {
    calories?: number;
    protein?: number;
    fat?: number;
    carbohydrates?: number;
};

interface UseTaskPollingOptions {
    maxDuration?: number;  // Max polling duration in ms (default: 60000)
    initialDelay?: number; // Initial delay between polls in ms (default: 2000)
    maxDelay?: number;     // Maximum delay between polls in ms (default: 5000)
    backoffMultiplier?: number; // Exponential backoff multiplier (default: 1.5)
}

interface UseTaskPollingReturn {
    status: TaskStatus;
    result: TaskResult | null;
    error: string | null;
    reset: () => void;
}

export function useTaskPolling(
    taskId: string | null,
    options: UseTaskPollingOptions = {}
): UseTaskPollingReturn {
    const {
        maxDuration = 60000,
        initialDelay = 2000,
        maxDelay = 5000,
        backoffMultiplier = 1.5,
    } = options;

    const [status, setStatus] = useState<TaskStatus>('idle');
    const [result, setResult] = useState<TaskResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const abortControllerRef = useRef<AbortController | null>(null);
    const timeoutIdRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const startTimeRef = useRef<number>(0);
    const isCancelledRef = useRef<boolean>(false);

    const reset = useCallback(() => {
        setStatus('idle');
        setResult(null);
        setError(null);
        isCancelledRef.current = true;
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }
        if (timeoutIdRef.current) {
            clearTimeout(timeoutIdRef.current);
            timeoutIdRef.current = null;
        }
    }, []);

    useEffect(() => {
        if (!taskId) {
            return;
        }

        // Reset state for new task
        setStatus('polling');
        setResult(null);
        setError(null);
        isCancelledRef.current = false;
        startTimeRef.current = Date.now();

        const controller = new AbortController();
        abortControllerRef.current = controller;

        const poll = async (attempt: number = 0) => {
            // Check if cancelled
            if (isCancelledRef.current || controller.signal.aborted) {
                return;
            }

            // Check timeout
            const elapsed = Date.now() - startTimeRef.current;
            if (elapsed >= maxDuration) {
                setStatus('timeout');
                setError('Превышено время ожидания распознавания. Попробуйте ещё раз.');
                return;
            }

            // Calculate backoff delay
            const delay = Math.min(initialDelay * Math.pow(backoffMultiplier, attempt), maxDelay);

            try {
                // Use unified API client instead of direct fetch
                const data: TaskStatusResponse = await ai.getTaskStatus(taskId);
                console.log(`[TaskPolling] Task ${taskId} state: ${data.state}`, data);

                if (data.state === 'SUCCESS') {
                    const result = data.result;

                    // Backend may return success: false with error message
                    if (result && result.success === false) {
                        setStatus('failed');
                        setError(result.error || 'AI не смог распознать еду на фото');
                        return;
                    }

                    // Extract data from task result (success=true case)
                    let recognizedItems = result?.recognized_items || [];

                    // Type-safe extraction of totals with proper type annotation
                    const totals: Totals = (result && result.success === true)
                        ? result.totals
                        : {};

                    // Type-safe extraction of meal_id - convert to string
                    const mealId = result?.meal_id;
                    const mealIdString = mealId !== undefined
                        ? String(mealId)
                        : '';

                    // FALLBACK: If recognized_items is empty but meal_id exists,
                    // the items may have been saved but not returned in task result
                    if (recognizedItems.length === 0 && mealIdString) {
                        console.log(`[TaskPolling] Empty recognized_items but meal_id=${mealIdString} exists`);
                        // Note: In hook we don't have access to api.getMealAnalysis
                        // The caller should handle this case by fetching meal directly
                    }

                    setStatus('success');
                    setResult({
                        success: true,
                        meal_id: mealIdString,
                        recognized_items: recognizedItems,
                        total_calories: totals.calories ?? 0,
                        total_protein: totals.protein ?? 0,
                        total_fat: totals.fat ?? 0,
                        total_carbohydrates: totals.carbohydrates ?? 0,
                        photo_url: result?.photo_url
                    });
                    return;
                }

                if (data.state === 'FAILURE') {
                    setStatus('failed');
                    setError(data.error || 'Ошибка обработки фото');
                    return;
                }

                // Task still processing (PENDING, STARTED, RETRY)
                // Continue polling with exponential backoff
                if (!controller.signal.aborted) {
                    timeoutIdRef.current = setTimeout(() => poll(attempt + 1), delay);
                }

            } catch (err: any) {
                if (controller.signal.aborted) {
                    // Polling was cancelled
                    return;
                }

                console.error(`[TaskPolling] Error polling task ${taskId}:`, err);

                // Network error - retry a few times
                if (attempt < 3) {
                    timeoutIdRef.current = setTimeout(() => poll(attempt + 1), delay);
                } else {
                    setStatus('failed');
                    setError('Ошибка сети. Проверьте подключение.');
                }
            }
        };

        // Start polling
        poll(0);

        // Cleanup
        return () => {
            controller.abort();
            if (timeoutIdRef.current) {
                clearTimeout(timeoutIdRef.current);
            }
        };
    }, [taskId, maxDuration, initialDelay, maxDelay, backoffMultiplier]);

    return { status, result, error, reset };
}
