import { useState, useEffect, useCallback, useRef } from 'react';
import { getTaskStatus, mapToAnalysisResult } from '../api';
import type { TaskStatusResponse, AnalysisResult } from '../api';
import { POLLING_CONFIG, getAiErrorMessage } from '../model';

export type PollingStatus = 'idle' | 'polling' | 'success' | 'failed' | 'timeout';

interface UseTaskPollingOptions {
    maxDuration?: number;
    initialDelay?: number;
    maxDelay?: number;
    backoffMultiplier?: number;
}

interface UseTaskPollingReturn {
    status: PollingStatus;
    result: AnalysisResult | null;
    error: string | null;
    reset: () => void;
}

const isAbortError = (err: any) => err?.name === 'AbortError' || err?.code === 'ERR_CANCELED';

export function useTaskPolling(
    taskId: string | null,
    options: UseTaskPollingOptions = {}
): UseTaskPollingReturn {
    const {
        maxDuration = POLLING_CONFIG.CLIENT_TIMEOUT_MS,
        initialDelay = POLLING_CONFIG.FAST_PHASE_DELAY_MS,
        maxDelay = POLLING_CONFIG.SLOW_PHASE_MAX_DELAY_MS,
        backoffMultiplier = POLLING_CONFIG.BACKOFF_MULTIPLIER,
    } = options;

    const [status, setStatus] = useState<PollingStatus>('idle');
    const [result, setResult] = useState<AnalysisResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    const abortRef = useRef<AbortController | null>(null);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const startRef = useRef<number>(0);

    const cleanupTimers = () => {
        if (timerRef.current) clearTimeout(timerRef.current);
        timerRef.current = null;
    };

    const reset = useCallback(() => {
        cleanupTimers();
        abortRef.current?.abort();
        abortRef.current = null;
        setStatus('idle');
        setResult(null);
        setError(null);
    }, []);

    useEffect(() => {
        if (!taskId) return;

        reset(); // сброс на новый taskId
        setStatus('polling');
        startRef.current = Date.now();

        const controller = new AbortController();
        abortRef.current = controller;

        const poll = async (attempt: number) => {
            if (controller.signal.aborted) return;

            const elapsed = Date.now() - startRef.current;
            if (elapsed >= maxDuration) {
                setStatus('timeout');
                setError('Превышено время ожидания распознавания. Попробуйте ещё раз.');
                return;
            }

            const delay = Math.min(initialDelay * Math.pow(backoffMultiplier, attempt), maxDelay);

            try {
                const data: TaskStatusResponse = await getTaskStatus(taskId, controller.signal);

                if (data.state === 'SUCCESS' && data.status === 'success') {
                    const mapped = mapToAnalysisResult(data);
                    if (!mapped) {
                        setStatus('failed');
                        const code = data.result?.error_code;
                        const msg = getAiErrorMessage(code, data.result?.error_message);
                        setError(msg);
                        return;
                    }
                    setStatus('success');
                    setResult(mapped);
                    return;
                }

                if (data.state === 'FAILURE' || data.status === 'failed') {
                    setStatus('failed');
                    const code = data.result?.error_code || data.error;
                    const msg = getAiErrorMessage(code, data.result?.error_message);
                    setError(msg);
                    return;
                }

                timerRef.current = setTimeout(() => poll(attempt + 1), delay);
            } catch (err: any) {
                if (controller.signal.aborted || isAbortError(err)) return;

                // лёгкий сетевой retry
                if (attempt < 3) {
                    timerRef.current = setTimeout(() => poll(attempt + 1), delay);
                    return;
                }

                setStatus('failed');
                setError(getAiErrorMessage('NETWORK_ERROR', err?.message));
            }
        };

        poll(0);

        return () => {
            cleanupTimers();
            controller.abort();
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [taskId, maxDuration, initialDelay, maxDelay, backoffMultiplier]);

    return { status, result, error, reset };
}
