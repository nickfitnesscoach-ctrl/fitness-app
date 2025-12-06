/**
 * Hook for polling AI recognition task status
 * Used when backend returns HTTP 202 (async mode)
 */

import { useState, useEffect, useCallback, useRef } from 'react';

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

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

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

    const reset = useCallback(() => {
        setStatus('idle');
        setResult(null);
        setError(null);
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
        startTimeRef.current = Date.now();

        const controller = new AbortController();
        abortControllerRef.current = controller;

        const poll = async (attempt: number = 0) => {
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
                // Build headers (same as in api.ts)
                const headers: HeadersInit = {
                    'Content-Type': 'application/json',
                };

                // Get Telegram init data if available
                if (typeof window !== 'undefined' && window.Telegram?.WebApp?.initData) {
                    headers['X-Telegram-Init-Data'] = window.Telegram.WebApp.initData;
                }

                const response = await fetch(`${API_BASE}/ai/task/${taskId}/`, {
                    method: 'GET',
                    headers,
                    signal: controller.signal,
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const data = await response.json();
                console.log(`[TaskPolling] Task ${taskId} state: ${data.state}`, data);

                if (data.state === 'SUCCESS' && data.result) {
                    // Task completed successfully
                    setStatus('success');
                    setResult(data.result);
                    return;
                }

                if (data.state === 'FAILURE') {
                    // Task failed
                    setStatus('failed');
                    setError(data.error || 'Ошибка распознавания');
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
