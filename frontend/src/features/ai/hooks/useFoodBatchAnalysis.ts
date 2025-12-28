/**
 * Sequential batch upload + polling with per-photo statuses.
 * Key rules:
 * - one-at-a-time processing
 * - AbortSignal passed everywhere
 * - hook OWNS previewUrl after startBatch() (creates & revokes)
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { recognizeFood, getTaskStatus, cancelAiTask, mapToAnalysisResult } from '../api';
import type { AnalysisResult, TaskStatusResponse, RecognizeResponse } from '../api';
import type { FileWithComment, BatchAnalysisOptions, PhotoQueueItem, PhotoUploadStatus } from '../model';
import { POLLING_CONFIG, AI_ERROR_CODES, NON_RETRYABLE_ERROR_CODES, getAiErrorMessage } from '../model';
import { preprocessImage, PreprocessError } from '../lib';
import { api } from '../../../services/api';

interface UseFoodBatchAnalysisResult {
    isProcessing: boolean;
    photoQueue: PhotoQueueItem[];
    startBatch: (files: FileWithComment[]) => Promise<void>;
    /** Mark single photo for retry (does NOT auto-start processing) */
    retryPhoto: (id: string) => void;
    /** Mark multiple photos for retry and start processing */
    retrySelected: (ids: string[]) => void;
    /** Manually start processing pending items */
    startProcessing: () => void;
    removePhoto: (id: string) => void;
    cancelBatch: () => void;
    cleanup: () => void;
}

const isAbortError = (err: any) => err?.name === 'AbortError' || err?.code === 'ERR_CANCELED';

const abortableSleep = (ms: number, signal: AbortSignal) =>
    new Promise<void>((resolve) => {
        if (signal.aborted) return resolve();
        const t = setTimeout(resolve, ms);
        const onAbort = () => {
            clearTimeout(t);
            signal.removeEventListener('abort', onAbort);
            resolve();
        };
        signal.addEventListener('abort', onAbort, { once: true });
    });

const getPollingDelay = (elapsedMs: number, attempt: number) => {
    if (elapsedMs < POLLING_CONFIG.FAST_PHASE_DURATION_MS) return POLLING_CONFIG.FAST_PHASE_DELAY_MS;

    const fastAttempts = Math.floor(POLLING_CONFIG.FAST_PHASE_DURATION_MS / POLLING_CONFIG.FAST_PHASE_DELAY_MS);
    const slowAttempt = Math.max(0, attempt - fastAttempts);

    const delay = POLLING_CONFIG.SLOW_PHASE_DELAY_MS * Math.pow(POLLING_CONFIG.BACKOFF_MULTIPLIER, slowAttempt);
    return Math.min(delay, POLLING_CONFIG.SLOW_PHASE_MAX_DELAY_MS);
};

export const useFoodBatchAnalysis = (options: BatchAnalysisOptions): UseFoodBatchAnalysisResult => {
    const [isProcessing, setIsProcessing] = useState(false);
    const [photoQueue, setPhotoQueue] = useState<PhotoQueueItem[]>([]);

    const isMountedRef = useRef(true);
    const queueRef = useRef<PhotoQueueItem[]>([]);
    const abortRef = useRef<AbortController | null>(null);
    const processingRef = useRef(false);
    const cancelledRef = useRef(false);

    const ownedUrlsRef = useRef<Set<string>>(new Set());

    useEffect(() => {
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    const setQueueSync = useCallback((updater: (prev: PhotoQueueItem[]) => PhotoQueueItem[]) => {
        const next = updater(queueRef.current);
        queueRef.current = next;
        if (isMountedRef.current) setPhotoQueue(next);
    }, []);

    const updatePhoto = useCallback(
        (id: string, patch: Partial<PhotoQueueItem>) => {
            if (cancelledRef.current) return;
            setQueueSync((prev) => prev.map((p) => (p.id === id ? { ...p, ...patch } : p)));
        },
        [setQueueSync]
    );

    const revokeOwnedUrls = useCallback(() => {
        ownedUrlsRef.current.forEach((url) => {
            try {
                URL.revokeObjectURL(url);
            } catch {
                // ignore
            }
        });
        ownedUrlsRef.current.clear();
    }, []);

    const pollTask = useCallback(async (taskId: string, controller: AbortController): Promise<AnalysisResult> => {
        const start = Date.now();
        let attempt = 0;

        while (!controller.signal.aborted && !cancelledRef.current) {
            const elapsed = Date.now() - start;
            if (elapsed >= POLLING_CONFIG.CLIENT_TIMEOUT_MS) {
                const e = new Error('Превышено время ожидания распознавания');
                (e as any).errorType = AI_ERROR_CODES.TASK_TIMEOUT;
                throw e;
            }

            const delay = getPollingDelay(elapsed, attempt);

            try {
                const status: TaskStatusResponse = await getTaskStatus(taskId, controller.signal);

                if (status.state === 'SUCCESS' && status.status === 'success') {
                    const mapped = mapToAnalysisResult(status);
                    if (!mapped) {
                        const e = new Error(status.result?.error_message || 'На фото не удалось распознать блюда');
                        (e as any).errorType = status.result?.error || AI_ERROR_CODES.EMPTY_RESULT;
                        throw e;
                    }
                    return mapped;
                }

                if (status.state === 'FAILURE' || status.status === 'failed') {
                    const e = new Error(status.result?.error_message || status.error || 'Ошибка обработки фото');
                    (e as any).errorType = status.result?.error || status.error || AI_ERROR_CODES.TASK_FAILURE;
                    throw e;
                }

                await abortableSleep(delay, controller.signal);
                attempt += 1;
            } catch (err: any) {
                if (controller.signal.aborted || cancelledRef.current) throw err;
                if (isAbortError(err)) throw err;

                // typed errors: just throw
                if (err?.errorType || err?.code === 'DAILY_LIMIT_REACHED') throw err;

                // small network retry
                if (attempt < 3) {
                    await abortableSleep(delay, controller.signal);
                    attempt += 1;
                    continue;
                }

                const e = new Error('Ошибка сети при получении результата');
                (e as any).errorType = AI_ERROR_CODES.NETWORK_ERROR;
                throw e;
            }
        }

        const e = new Error('Отменено');
        (e as any).errorType = AI_ERROR_CODES.CANCELLED;
        throw e;
    }, []);

    const processOne = useCallback(
        async (item: PhotoQueueItem, controller: AbortController) => {
            const { id, file, comment } = item;
            if (cancelledRef.current || controller.signal.aborted) return;

            try {
                updatePhoto(id, { status: 'compressing' });

                const pre = await preprocessImage(file);
                if (cancelledRef.current || controller.signal.aborted) return;

                updatePhoto(id, { status: 'uploading' });

                const dateStr = options.getDateString();
                const mealType = String(options.getMealType()).toLowerCase();

                const rr: RecognizeResponse = await recognizeFood(
                    pre.file,
                    comment,
                    mealType,
                    dateStr,
                    controller.signal
                );

                if (cancelledRef.current || controller.signal.aborted) return;

                updatePhoto(id, { status: 'processing', taskId: rr.task_id, mealId: rr.meal_id ?? undefined });

                const analysis = await pollTask(rr.task_id, controller);

                updatePhoto(id, { status: 'success', result: analysis });
            } catch (err: any) {
                if (cancelledRef.current || controller.signal.aborted) return;
                if (isAbortError(err)) return;

                // daily limit
                if (err?.code === 'DAILY_LIMIT_REACHED') {
                    options.onDailyLimitReached?.();
                    updatePhoto(id, {
                        status: 'error',
                        errorCode: AI_ERROR_CODES.DAILY_LIMIT_REACHED,
                        error: getAiErrorMessage(AI_ERROR_CODES.DAILY_LIMIT_REACHED),
                    });
                    controller.abort();
                    return;
                }

                if (err instanceof PreprocessError) {
                    updatePhoto(id, {
                        status: 'error',
                        errorCode: err.code,
                        error: getAiErrorMessage(err.code),
                    });
                    return;
                }

                const errorCode = err?.errorType || err?.code || AI_ERROR_CODES.TASK_FAILURE;
                const msg = getAiErrorMessage(errorCode);
                updatePhoto(id, { status: 'error', errorCode, error: msg });
            }
        },
        [options, pollTask, updatePhoto]
    );

    const getNextPending = useCallback(() => queueRef.current.find((p) => p.status === 'pending') || null, []);

    const processQueue = useCallback(
        async (controller: AbortController) => {
            while (!controller.signal.aborted && !cancelledRef.current) {
                const next = getNextPending();
                if (!next) break;
                await processOne(next, controller);
            }
        },
        [getNextPending, processOne]
    );

    const startBatch = useCallback(
        async (files: FileWithComment[]) => {
            if (processingRef.current) return;

            // new run
            cancelledRef.current = false;
            processingRef.current = true;
            setIsProcessing(true);

            // reset owned urls
            revokeOwnedUrls();

            const controller = new AbortController();
            abortRef.current = controller;

            const initial: PhotoQueueItem[] = files.map((f) => {
                // hook takes ownership: always create preview if missing
                const previewUrl = f.previewUrl || URL.createObjectURL(f.file);
                ownedUrlsRef.current.add(previewUrl);

                return {
                    id: crypto.randomUUID(),
                    file: f.file,
                    comment: f.comment,
                    previewUrl,
                    status: 'pending' as PhotoUploadStatus,
                };
            });

            setQueueSync(() => initial);

            try {
                await processQueue(controller);
            } finally {
                abortRef.current = null;
                processingRef.current = false;
                if (isMountedRef.current) setIsProcessing(false);
            }
        },
        [processQueue, revokeOwnedUrls, setQueueSync]
    );

    const retryPhoto = useCallback(
        (id: string) => {
            const photo = queueRef.current.find((p) => p.id === id);
            // Only error status is retryable
            if (!photo || photo.status !== 'error') return;
            // Block non-retryable error codes (e.g., daily limit)
            if (photo.errorCode && NON_RETRYABLE_ERROR_CODES.has(photo.errorCode)) return;

            // Just mark as pending, don't auto-start (multi-select mode)
            setQueueSync((prev) =>
                prev.map((p) =>
                    p.id === id
                        ? { ...p, status: 'pending' as PhotoUploadStatus, errorCode: undefined, error: undefined, result: undefined, taskId: undefined, mealId: undefined }
                        : p
                )
            );
        },
        [setQueueSync]
    );

    /** Mark multiple photos for retry and immediately start processing */
    const retrySelected = useCallback(
        (ids: string[]) => {
            if (ids.length === 0) return;
            if (processingRef.current) return;

            // Mark all selected as pending
            const validIds = new Set(ids);
            setQueueSync((prev) =>
                prev.map((p) => {
                    if (!validIds.has(p.id)) return p;
                    if (p.status !== 'error') return p;
                    if (p.errorCode && NON_RETRYABLE_ERROR_CODES.has(p.errorCode)) return p;
                    return { ...p, status: 'pending' as PhotoUploadStatus, errorCode: undefined, error: undefined, result: undefined, taskId: undefined, mealId: undefined };
                })
            );

            // Start processing
            cancelledRef.current = false;
            processingRef.current = true;
            setIsProcessing(true);

            const controller = new AbortController();
            abortRef.current = controller;

            processQueue(controller).finally(() => {
                abortRef.current = null;
                processingRef.current = false;
                if (isMountedRef.current) setIsProcessing(false);
            });
        },
        [processQueue, setQueueSync]
    );

    /** Manually start processing pending items (for multi-select flow) */
    const startProcessing = useCallback(() => {
        if (processingRef.current) return;
        const hasPending = queueRef.current.some((p) => p.status === 'pending');
        if (!hasPending) return;

        cancelledRef.current = false;
        processingRef.current = true;
        setIsProcessing(true);

        const controller = new AbortController();
        abortRef.current = controller;

        processQueue(controller).finally(() => {
            abortRef.current = null;
            processingRef.current = false;
            if (isMountedRef.current) setIsProcessing(false);
        });
    }, [processQueue]);

    const removePhoto = useCallback(
        (id: string) => {
            setQueueSync((prev) => {
                const item = prev.find((p) => p.id === id);
                if (item?.previewUrl && ownedUrlsRef.current.has(item.previewUrl)) {
                    try {
                        URL.revokeObjectURL(item.previewUrl);
                    } catch { }
                    ownedUrlsRef.current.delete(item.previewUrl);
                }
                return prev.filter((p) => p.id !== id);
            });
        },
        [setQueueSync]
    );

    const cancelBatch = useCallback(() => {
        cancelledRef.current = true;
        abortRef.current?.abort();
        abortRef.current = null;

        // Collect taskIds to cancel on backend and mealIds to delete
        const taskIdsToCancel: string[] = [];
        const mealIdsToDelete: number[] = [];
        queueRef.current.forEach((p) => {
            // Cancel tasks that are in-flight (uploading/processing with taskId)
            if (p.taskId && p.status !== 'success' && p.status !== 'error') {
                taskIdsToCancel.push(p.taskId);
            }
            // Also try to delete meals (best effort)
            if (p.mealId && p.status !== 'success' && p.status !== 'error') {
                mealIdsToDelete.push(p.mealId);
            }
        });

        setQueueSync((prev) =>
            prev.map((p) => {
                if (p.status === 'success' || p.status === 'error') return p;
                return {
                    ...p,
                    status: 'error' as const,
                    errorCode: AI_ERROR_CODES.CANCELLED,
                    error: getAiErrorMessage(AI_ERROR_CODES.CANCELLED),
                };
            })
        );

        // Cancel tasks on backend (fire-and-forget) - prevents meal creation
        taskIdsToCancel.forEach((taskId) => {
            void cancelAiTask(taskId);
        });

        // Delete orphan meals from server (fire-and-forget, best effort)
        mealIdsToDelete.forEach((mealId) => {
            api.deleteMeal(mealId).catch((err) => {
                console.warn('[cancelBatch] Failed to delete meal', mealId, err);
            });
        });

        processingRef.current = false;
        if (isMountedRef.current) setIsProcessing(false);
    }, [setQueueSync]);

    const cleanup = useCallback(() => {
        cancelledRef.current = true;
        abortRef.current?.abort();
        abortRef.current = null;

        processingRef.current = false;
        if (isMountedRef.current) setIsProcessing(false);

        revokeOwnedUrls();
        setQueueSync(() => []);
    }, [revokeOwnedUrls, setQueueSync]);

    return {
        isProcessing,
        photoQueue,
        startBatch,
        retryPhoto,
        retrySelected,
        startProcessing,
        removePhoto,
        cancelBatch,
        cleanup,
    };
};
