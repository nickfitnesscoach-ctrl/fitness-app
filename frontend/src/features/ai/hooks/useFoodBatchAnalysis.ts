/**
 * Hook for managing batch food photo analysis with per-photo status tracking
 *
 * Features:
 * - Sequential processing (1-at-a-time)
 * - Per-photo status updates
 * - 2-phase polling (fast first 15s, then slow with backoff)
 * - Retry for individual failed photos (works during active batch)
 * - Proper cancellation (AbortController passed everywhere + abortable sleeps)
 * - Own URL management (creates and revokes preview URLs)
 *
 * Notes:
 * - Hook "owns" previewUrl for items passed into startBatch from that moment.
 *   Parent MUST NOT revoke previewUrl after calling startBatch.
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { recognizeFood, getTaskStatus, mapToAnalysisResult } from '../api';
import type { AnalysisResult, TaskStatusResponse } from '../api';
import type {
    FileWithComment,
    BatchAnalysisOptions,
    PhotoQueueItem,
    PhotoUploadStatus,
} from '../model';
import { POLLING_CONFIG, AI_ERROR_CODES, getAiErrorMessage } from '../model';
import { preprocessImage, PreprocessError } from '../lib';

// ============================================================
// Hook Interface
// ============================================================

interface UseFoodBatchAnalysisResult {
    isProcessing: boolean;
    photoQueue: PhotoQueueItem[];
    startBatch: (files: FileWithComment[]) => Promise<void>;
    retryPhoto: (id: string) => void;
    removePhoto: (id: string) => void;
    cancelBatch: () => void;
    cleanup: () => void;
}

// ============================================================
// Helpers
// ============================================================

const generatePhotoId = (): string => {
    return crypto.randomUUID();
};

const getPollingDelay = (elapsedMs: number, attempt: number): number => {
    if (elapsedMs < POLLING_CONFIG.FAST_PHASE_DURATION_MS) {
        return POLLING_CONFIG.FAST_PHASE_DELAY_MS;
    }
    const fastAttempts = Math.floor(
        POLLING_CONFIG.FAST_PHASE_DURATION_MS / POLLING_CONFIG.FAST_PHASE_DELAY_MS
    );
    const slowAttempt = Math.max(0, attempt - fastAttempts);
    const delay =
        POLLING_CONFIG.SLOW_PHASE_DELAY_MS *
        Math.pow(POLLING_CONFIG.BACKOFF_MULTIPLIER, slowAttempt);
    return Math.min(delay, POLLING_CONFIG.SLOW_PHASE_MAX_DELAY_MS);
};

const abortableSleep = (ms: number, signal: AbortSignal): Promise<void> =>
    new Promise<void>((resolve) => {
        if (signal.aborted) return resolve();

        const onAbort = () => {
            clearTimeout(timer);
            signal.removeEventListener('abort', onAbort);
            resolve();
        };

        const timer = setTimeout(() => {
            signal.removeEventListener('abort', onAbort);
            resolve();
        }, ms);

        signal.addEventListener('abort', onAbort, { once: true });
    });

const isAbortError = (err: any) =>
    err?.name === 'AbortError' || err?.code === 'ERR_CANCELED';

// ============================================================
// Main Hook
// ============================================================

export const useFoodBatchAnalysis = (
    options: BatchAnalysisOptions
): UseFoodBatchAnalysisResult => {
    const [isProcessing, setIsProcessing] = useState(false);
    const [photoQueue, setPhotoQueue] = useState<PhotoQueueItem[]>([]);

    // lifecycle + run guards
    const isMountedRef = useRef(true);
    const isCancelledRef = useRef(false);
    const processingRef = useRef(false);
    const runIdRef = useRef(0);

    // current queue snapshot (source of truth for async loops)
    const queueRef = useRef<PhotoQueueItem[]>([]);

    // abort + owned URLs
    const abortControllerRef = useRef<AbortController | null>(null);
    const ownedUrlsRef = useRef<Set<string>>(new Set());

    useEffect(() => {
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    const setStateSafe = useCallback((fn: () => void) => {
        if (!isMountedRef.current) return;
        fn();
    }, []);

    /**
     * Single "state setter" that keeps queueRef and state in sync.
     * Never uses React state closure in async flows.
     */
    const setPhotoQueueSync = useCallback(
        (updater: (prev: PhotoQueueItem[]) => PhotoQueueItem[]) => {
            const next = updater(queueRef.current);
            queueRef.current = next;
            if (isMountedRef.current) setPhotoQueue(next);
        },
        []
    );

    const updatePhoto = useCallback(
        (id: string, patch: Partial<PhotoQueueItem>) => {
            if (isCancelledRef.current) return;
            setPhotoQueueSync((prev) =>
                prev.map((p) => (p.id === id ? { ...p, ...patch } : p))
            );
        },
        [setPhotoQueueSync]
    );

    const resetOwnedUrls = useCallback(() => {
        ownedUrlsRef.current.forEach((url) => {
            try {
                URL.revokeObjectURL(url);
            } catch {
                /* ignore */
            }
        });
        ownedUrlsRef.current.clear();
    }, []);

    const pollTaskStatus = useCallback(
        async (
            taskId: string,
            abortController: AbortController
        ): Promise<AnalysisResult | null> => {
            const startTime = Date.now();
            let attempt = 0;

            while (!abortController.signal.aborted && !isCancelledRef.current) {
                const elapsed = Date.now() - startTime;

                if (elapsed >= POLLING_CONFIG.CLIENT_TIMEOUT_MS) {
                    const timeoutError = new Error('Превышено время ожидания распознавания');
                    (timeoutError as any).errorType = AI_ERROR_CODES.TASK_TIMEOUT;
                    throw timeoutError;
                }

                const delay = getPollingDelay(elapsed, attempt);

                try {
                    const taskStatus: TaskStatusResponse = await getTaskStatus(
                        taskId,
                        abortController.signal
                    );

                    // SUCCESS state (might contain logic error)
                    if (taskStatus.state === 'SUCCESS' && taskStatus.status === 'success') {
                        const analysisResult = mapToAnalysisResult(taskStatus);

                        // P0-Contract Check: Fail if mapping resulted in null (empty items/error)
                        if (!analysisResult) {
                            const errorCode = taskStatus.result?.error || AI_ERROR_CODES.EMPTY_RESULT;
                            const failError = new Error(taskStatus.result?.error_message || 'На фото не удалось распознать блюда');
                            (failError as any).errorType = errorCode;
                            throw failError;
                        }

                        return analysisResult;
                    }

                    // FAILURE or controlled error from backend
                    if (taskStatus.state === 'FAILURE' || taskStatus.status === 'failed') {
                        const errorCode = taskStatus.error || AI_ERROR_CODES.TASK_FAILURE;
                        const failError = new Error(taskStatus.result?.error_message || errorCode);
                        (failError as any).errorType = errorCode;
                        throw failError;
                    }

                    // Still processing
                    await abortableSleep(delay, abortController.signal);
                    attempt += 1;
                } catch (err: any) {
                    if (abortController.signal.aborted || isCancelledRef.current) return null;
                    if (isAbortError(err)) return null;

                    // Rethrow known typed errors
                    if (err?.errorType || err?.code === 'DAILY_LIMIT_REACHED') throw err;

                    // Network-ish retry a few times
                    if (attempt < 3) {
                        await abortableSleep(delay, abortController.signal);
                        attempt += 1;
                        continue;
                    }

                    const networkError = new Error('Ошибка сети при получении результата');
                    (networkError as any).errorType = AI_ERROR_CODES.NETWORK_ERROR;
                    throw networkError;
                }
            }

            return null;
        },
        []
    );

    const processPhoto = useCallback(
        async (item: PhotoQueueItem, abortController: AbortController): Promise<void> => {
            const { id, file, comment } = item;
            if (isCancelledRef.current) return;

            try {
                // Stage 1: Compressing
                updatePhoto(id, { status: 'compressing' });

                const { file: processedFile } = await preprocessImage(file);
                if (abortController.signal.aborted || isCancelledRef.current) return;

                // Stage 2: Uploading
                updatePhoto(id, { status: 'uploading' });

                const dateStr = options.getDateString();
                const mealTypeValue = options.getMealType().toLowerCase();

                const recognizeResponse = await recognizeFood(
                    processedFile,
                    comment,
                    mealTypeValue,
                    dateStr,
                    abortController.signal
                );

                if (abortController.signal.aborted || isCancelledRef.current) return;

                // Stage 3: Processing
                updatePhoto(id, {
                    status: 'processing',
                    taskId: recognizeResponse.task_id,
                    mealId: recognizeResponse.meal_id,
                });

                const result = await pollTaskStatus(
                    recognizeResponse.task_id,
                    abortController
                );

                if (!result || isCancelledRef.current) return;

                // Stage 4: Success / Error
                updatePhoto(id, { status: 'success', result });
            } catch (err: any) {
                if (isCancelledRef.current || abortController.signal.aborted) return;
                if (isAbortError(err)) return;

                // Daily limit
                if (
                    err?.code === AI_ERROR_CODES.DAILY_LIMIT_REACHED ||
                    err?.error === AI_ERROR_CODES.DAILY_LIMIT_REACHED
                ) {
                    options.onDailyLimitReached?.();
                    updatePhoto(id, {
                        status: 'error',
                        error: getAiErrorMessage(AI_ERROR_CODES.DAILY_LIMIT_REACHED),
                    });
                    abortController.abort();
                    return;
                }

                // Preprocess errors
                if (err instanceof PreprocessError) {
                    updatePhoto(id, { status: 'error', error: getAiErrorMessage(err.code) });
                    return;
                }

                // General
                const msg = getAiErrorMessage(err?.errorType || err?.error || err?.message);
                updatePhoto(id, { status: 'error', error: msg });
            }
        },
        [options, pollTaskStatus, updatePhoto]
    );

    const getNextPendingPhoto = useCallback((): PhotoQueueItem | null => {
        return queueRef.current.find((p) => p.status === 'pending') || null;
    }, []);

    const processQueue = useCallback(
        async (abortController: AbortController): Promise<void> => {
            while (!abortController.signal.aborted && !isCancelledRef.current) {
                const next = getNextPendingPhoto();
                if (!next) break;
                await processPhoto(next, abortController);
            }
        },
        [getNextPendingPhoto, processPhoto]
    );

    const finalizeRun = useCallback(
        (runId: number) => {
            if (runIdRef.current !== runId) return;
            processingRef.current = false;
            abortControllerRef.current = null;
            setStateSafe(() => setIsProcessing(false));
        },
        [setStateSafe]
    );

    const startBatch = useCallback(
        async (filesWithComments: FileWithComment[]): Promise<void> => {
            if (processingRef.current) {
                console.warn('[Queue] Already processing, ignoring startBatch');
                return;
            }

            // New run
            resetOwnedUrls();
            isCancelledRef.current = false;

            runIdRef.current += 1;
            const runId = runIdRef.current;

            processingRef.current = true;
            setStateSafe(() => setIsProcessing(true));

            const abortController = new AbortController();
            abortControllerRef.current = abortController;

            const initialQueue: PhotoQueueItem[] = filesWithComments.map((item) => {
                const previewUrl = item.previewUrl || URL.createObjectURL(item.file);
                ownedUrlsRef.current.add(previewUrl);

                return {
                    id: generatePhotoId(),
                    file: item.file,
                    comment: item.comment,
                    previewUrl,
                    status: 'pending' as PhotoUploadStatus,
                };
            });

            setPhotoQueueSync(() => initialQueue);

            try {
                await processQueue(abortController);
            } finally {
                finalizeRun(runId);
            }
        },
        [finalizeRun, processQueue, resetOwnedUrls, setPhotoQueueSync, setStateSafe]
    );

    const retryPhoto = useCallback(
        (id: string): void => {
            const photo = queueRef.current.find((p) => p.id === id);
            if (!photo || photo.status !== 'error') return;
            if (photo.error === 'Отменено') return;

            setPhotoQueueSync((prev) =>
                prev.map((p) =>
                    p.id === id
                        ? {
                            ...p,
                            status: 'pending' as PhotoUploadStatus,
                            error: undefined,
                            result: undefined,
                            taskId: undefined,
                            mealId: undefined,
                        }
                        : p
                )
            );

            // If nothing is running, spin up a new run over existing queue
            if (!processingRef.current && abortControllerRef.current === null) {
                isCancelledRef.current = false;

                runIdRef.current += 1;
                const runId = runIdRef.current;

                processingRef.current = true;
                setStateSafe(() => setIsProcessing(true));

                const abortController = new AbortController();
                abortControllerRef.current = abortController;

                processQueue(abortController).finally(() => finalizeRun(runId));
            }
        },
        [finalizeRun, processQueue, setPhotoQueueSync, setStateSafe]
    );

    const removePhoto = useCallback(
        (id: string): void => {
            setPhotoQueueSync((prev) => {
                const item = prev.find((p) => p.id === id);
                if (item?.previewUrl && ownedUrlsRef.current.has(item.previewUrl)) {
                    try {
                        URL.revokeObjectURL(item.previewUrl);
                    } catch {
                        /* ignore */
                    }
                    ownedUrlsRef.current.delete(item.previewUrl);
                }
                return prev.filter((p) => p.id !== id);
            });
        },
        [setPhotoQueueSync]
    );

    const cancelBatch = useCallback((): void => {
        isCancelledRef.current = true;

        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            // keep it non-null until finalizeRun? we can null it now safely
            abortControllerRef.current = null;
        }

        // Mark in-flight items as cancelled (no retry)
        setPhotoQueueSync((prev) =>
            prev.map((p) => {
                if (p.status === 'success' || p.status === 'error') return p;
                return { ...p, status: 'error' as const, error: 'Отменено' };
            })
        );

        processingRef.current = false;
        setStateSafe(() => setIsProcessing(false));
    }, [setPhotoQueueSync, setStateSafe]);

    const cleanup = useCallback((): void => {
        // hard stop
        isCancelledRef.current = true;

        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            abortControllerRef.current = null;
        }

        resetOwnedUrls();

        processingRef.current = false;
        setStateSafe(() => setIsProcessing(false));
        setPhotoQueueSync(() => []);
    }, [resetOwnedUrls, setPhotoQueueSync, setStateSafe]);

    return {
        isProcessing,
        photoQueue,
        startBatch,
        retryPhoto,
        removePhoto,
        cancelBatch,
        cleanup,
    };
};
