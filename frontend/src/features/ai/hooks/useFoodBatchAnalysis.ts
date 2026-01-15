/**
 * Sequential batch upload + polling with per-photo statuses.
 *
 * Multi-Photo Meal Support:
 * - First photo creates a meal, subsequent photos attach to the same meal
 * - meal_id is tracked across the batch and passed to recognizeFood()
 * - Backend groups photos within 10-minute window automatically
 *
 * Key rules:
 * - one-at-a-time processing
 * - AbortSignal passed everywhere
 * - hook OWNS previewUrl after startBatch() (creates & revokes)
 */

import { useState, useRef, useCallback, useEffect } from 'react';
import { recognizeFood, getTaskStatus, cancelAiTask, mapToAnalysisResult, normalizeTaskStatus } from '../api';
import type { AnalysisResult, TaskStatusResponse, RecognizeResponse } from '../api';
import type { FileWithComment, BatchAnalysisOptions, PhotoQueueItem, PhotoUploadStatus } from '../model';
import { POLLING_CONFIG, AI_ERROR_CODES, NON_RETRYABLE_ERROR_CODES, getAiErrorMessage } from '../model';
import { preprocessImage, PreprocessError } from '../lib';
import { api } from '../../../services/api';

interface UseFoodBatchAnalysisResult {
    isProcessing: boolean;
    photoQueue: PhotoQueueItem[];
    startBatch: (files: FileWithComment[], context: { date: string; mealType: string; mealId?: number; mealPhotoId?: number }) => Promise<void>;
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

    // Store context for processing (date, mealType)
    const contextRef = useRef<{ date: string; mealType: string }>({ date: '', mealType: '' });

    // Multi-photo meal grouping: track meal_id for the batch
    const batchMealIdRef = useRef<number | undefined>(undefined);

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
        const maxAttempts = Math.ceil(POLLING_CONFIG.CLIENT_TIMEOUT_MS / POLLING_CONFIG.FAST_PHASE_DELAY_MS);

        while (!controller.signal.aborted && !cancelledRef.current) {
            const elapsed = Date.now() - start;

            // P0: Client timeout (120s hard limit)
            if (elapsed >= POLLING_CONFIG.CLIENT_TIMEOUT_MS) {
                const e = new Error('Превышено время ожидания распознавания');
                (e as any).errorType = AI_ERROR_CODES.TASK_TIMEOUT;
                throw e;
            }

            // P0: Max attempts guard (prevents infinite loop even if server never returns terminal status)
            if (attempt >= maxAttempts) {
                const e = new Error('Слишком много попыток проверки статуса');
                (e as any).errorType = AI_ERROR_CODES.TASK_TIMEOUT;
                throw e;
            }

            const delay = getPollingDelay(elapsed, attempt);

            try {
                const status: TaskStatusResponse = await getTaskStatus(taskId, controller.signal);

                // P0: Normalize status using SSOT helper
                const normalized = normalizeTaskStatus(status);
                console.log(`[AI] Task ${taskId} normalized status: ${normalized} (raw: state=${status.state}, status=${status.status})`);

                if (normalized === 'SUCCESS') {
                    console.log(`[AI] Task ${taskId} SUCCESS - mapping result`);
                    const mapped = mapToAnalysisResult(status);
                    if (!mapped) {
                        console.warn(`[AI] Task ${taskId} SUCCESS but mapping failed:`, status.result);
                        const e = new Error(status.result?.error_message || 'На фото не удалось распознать блюда');
                        (e as any).errorType = status.result?.error || AI_ERROR_CODES.EMPTY_RESULT;
                        throw e;
                    }
                    console.log(`[AI] Task ${taskId} mapped successfully:`, mapped);

                    // P0: Dispatch global event to refresh meals cache
                    // This ensures diary/meal cards update immediately without waiting for modal close
                    window.dispatchEvent(new CustomEvent('ai:photo-success', {
                        detail: { taskId, mealId: mapped.meal_id }
                    }));

                    return mapped;
                }

                if (normalized === 'FAILED') {
                    console.error(`[AI] Task ${taskId} FAILED:`, status.error || status.result?.error_message);

                    // P1.5: Dispatch event on FAILED to refresh meal card state
                    window.dispatchEvent(new CustomEvent('ai:photo-failed', {
                        detail: { taskId, error: status.error || status.result?.error_message }
                    }));

                    const e = new Error(status.result?.error_message || status.error || 'Ошибка обработки фото');
                    (e as any).errorType = status.result?.error || status.error || AI_ERROR_CODES.TASK_FAILURE;
                    throw e;
                }

                // Continue polling (PENDING/PROCESSING)
                console.log(`[AI] Task ${taskId} still processing (attempt ${attempt + 1}/${maxAttempts}, elapsed ${elapsed}ms)`);
                await abortableSleep(delay, controller.signal);
                attempt += 1;
            } catch (err: any) {
                if (controller.signal.aborted || cancelledRef.current) throw err;
                if (isAbortError(err)) throw err;

                // typed errors: just throw (terminal states)
                if (err?.errorType || err?.code === 'DAILY_LIMIT_REACHED') throw err;

                // small network retry (only for network errors, not logic errors)
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

                // Use context from ref
                const dateStr = contextRef.current.date || new Date().toISOString().split('T')[0];
                const mealType = contextRef.current.mealType || 'snack';

                // Multi-photo grouping: pass meal_id from previous photos in batch
                // Retry: pass meal_photo_id if retrying existing failed photo
                const rr: RecognizeResponse = await recognizeFood(
                    pre.file,
                    comment,
                    mealType,
                    dateStr,
                    controller.signal,
                    item.mealId ?? batchMealIdRef.current, // Use item's mealId for retry, or batch ref for new
                    item.mealPhotoId // Pass existing photo ID for retry (prevents duplicate)
                );

                if (cancelledRef.current || controller.signal.aborted) return;

                // Store meal_id for subsequent photos in the batch
                if (rr.meal_id && !batchMealIdRef.current) {
                    batchMealIdRef.current = rr.meal_id;
                }

                updatePhoto(id, {
                    status: 'processing',
                    taskId: rr.task_id,
                    mealId: rr.meal_id ?? undefined,
                    mealPhotoId: rr.meal_photo_id ?? undefined
                });

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
        async (files: FileWithComment[], context: { date: string; mealType: string; mealId?: number; mealPhotoId?: number }) => {
            if (processingRef.current) return;

            // Save context for processing
            contextRef.current = context;

            // Reset or restore meal_id for new batch
            batchMealIdRef.current = context.mealId;

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

                const item: PhotoQueueItem = {
                    id: Math.random().toString(36).substring(7),
                    file: f.file,
                    comment: f.comment,
                    previewUrl,
                    status: 'pending' as PhotoUploadStatus,
                    mealId: context.mealId,
                    mealPhotoId: context.mealPhotoId,
                };
                return item;
            });

            setQueueSync(() => initial);

            // Small delay to ensure UI updates before processing starts
            await new Promise(resolve => setTimeout(resolve, 50));

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
            // IMPORTANT: Keep mealId and mealPhotoId for retry (prevents duplicate MealPhoto)
            setQueueSync((prev) =>
                prev.map((p) =>
                    p.id === id
                        ? { ...p, status: 'pending' as PhotoUploadStatus, errorCode: undefined, error: undefined, result: undefined, taskId: undefined }
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
            // IMPORTANT: Keep mealId and mealPhotoId for retry (prevents duplicate MealPhoto)
            const validIds = new Set(ids);
            setQueueSync((prev) =>
                prev.map((p) => {
                    if (!validIds.has(p.id)) return p;
                    if (p.status !== 'error') return p;
                    if (p.errorCode && NON_RETRYABLE_ERROR_CODES.has(p.errorCode)) return p;
                    return { ...p, status: 'pending' as PhotoUploadStatus, errorCode: undefined, error: undefined, result: undefined, taskId: undefined };
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

        // Collect taskIds to cancel on backend (in-flight only)
        const taskIdsToCancel: string[] = [];
        queueRef.current.forEach((p) => {
            if (p.taskId && !['success', 'error'].includes(p.status)) {
                taskIdsToCancel.push(p.taskId);
            }
        });

        // Cancel tasks on backend (fire-and-forget)
        taskIdsToCancel.forEach((taskId) => {
            void cancelAiTask(taskId);
        });

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
