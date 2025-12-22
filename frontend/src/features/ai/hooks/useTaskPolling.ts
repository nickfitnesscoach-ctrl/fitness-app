/**
 * Hook for polling AI recognition task status
 * Used when backend returns HTTP 202 (async mode)
 *
 * Aligned with API Contract:
 * - GET /api/v1/ai/task/<id>/
 * - Uses state+status fields
 * - Handles items (not recognized_items)
 * - Maps amount_grams to grams
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { getTaskStatus, mapToAnalysisResult } from '../api';
import type { TaskStatusResponse, AnalysisResult } from '../api';
import { POLLING_CONFIG } from '../model';

export type PollingStatus = 'idle' | 'polling' | 'success' | 'failed' | 'timeout';

interface UseTaskPollingOptions {
    /** Max polling duration in ms (default: 60000) */
    maxDuration?: number;
    /** Initial delay between polls in ms (default: 1500) */
    initialDelay?: number;
    /** Maximum delay between polls in ms (default: 5000) */
    maxDelay?: number;
    /** Exponential backoff multiplier (default: 1.5) */
    backoffMultiplier?: number;
}

interface UseTaskPollingReturn {
    status: PollingStatus;
    result: AnalysisResult | null;
    error: string | null;
    reset: () => void;
}

export function useTaskPolling(
    taskId: string | null,
    options: UseTaskPollingOptions = {}
): UseTaskPollingReturn {
    const {
        maxDuration = POLLING_CONFIG.CLIENT_TIMEOUT_MS,
        initialDelay = POLLING_CONFIG.INITIAL_DELAY_MS,
        maxDelay = POLLING_CONFIG.MAX_DELAY_MS,
        backoffMultiplier = POLLING_CONFIG.BACKOFF_MULTIPLIER,
    } = options;

    const [status, setStatus] = useState<PollingStatus>('idle');
    const [result, setResult] = useState<AnalysisResult | null>(null);
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
                const data: TaskStatusResponse = await getTaskStatus(taskId);
                console.log(`[TaskPolling] Task ${taskId}: state=${data.state}, status=${data.status}`);

                // SUCCESS state
                if (data.state === 'SUCCESS' && data.status === 'success') {
                    // Map API result to UI format
                    const analysisResult = mapToAnalysisResult(data.result);

                    if (!analysisResult || analysisResult.recognized_items.length === 0) {
                        // Empty result with meal_id is okay - still "success" for UI
                        if (data.result?.meal_id) {
                            setStatus('success');
                            setResult({
                                meal_id: data.result.meal_id,
                                recognized_items: [],
                                total_calories: 0,
                                total_protein: 0,
                                total_fat: 0,
                                total_carbohydrates: 0,
                                _neutralMessage: 'Анализ завершён, проверьте дневник',
                            });
                            return;
                        }
                        // No meal_id and no items = failure
                        setStatus('failed');
                        setError('Мы не смогли распознать еду на фото');
                        return;
                    }

                    setStatus('success');
                    setResult(analysisResult);
                    return;
                }

                // FAILURE state
                if (data.state === 'FAILURE' || data.status === 'failed') {
                    setStatus('failed');
                    setError(data.error || 'Ошибка обработки фото');
                    return;
                }

                // Still processing (PENDING, STARTED, RETRY) - continue polling
                if (!controller.signal.aborted) {
                    timeoutIdRef.current = setTimeout(() => poll(attempt + 1), delay);
                }

            } catch (err: any) {
                if (controller.signal.aborted) {
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
