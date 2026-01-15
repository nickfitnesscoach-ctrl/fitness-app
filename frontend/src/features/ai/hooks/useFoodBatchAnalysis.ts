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
import { recognizeFood, getTaskStatus, cancelAiTask, cancelAiProcessing, mapToAnalysisResult, normalizeTaskStatus } from '../api';
import type { AnalysisResult, TaskStatusResponse, RecognizeResponse, CancelRequest } from '../api';
import type { FileWithComment, BatchAnalysisOptions, PhotoQueueItem, PhotoUploadStatus } from '../model';
import { POLLING_CONFIG, AI_ERROR_CODES, NON_RETRYABLE_ERROR_CODES, getAiErrorMessage } from '../model';
import { preprocessImage, PreprocessError, generateUUID } from '../lib';
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

// ============================================================
// P1.2: Unified Status Helpers
// ============================================================

/** Status that means processing is still active */
export const isInFlightStatus = (s: PhotoUploadStatus): boolean =>
    s === 'pending' || s === 'compressing' || s === 'uploading' || s === 'processing';

/** Terminal state - no more changes expected */
export const isTerminalStatus = (s: PhotoUploadStatus): boolean =>
    s === 'success' || s === 'error' || s === 'cancelled';

/** Result worth showing to user (success or error, not cancelled) */
export const isResultStatus = (s: PhotoUploadStatus): boolean =>
    s === 'success' || s === 'error';

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
    // P1.2: runId to invalidate stale promises from cancelled/restarted batches
    const runIdRef = useRef(0);

    const ownedUrlsRef = useRef<Set<string>>(new Set());

    useEffect(() => {
        // P0 FIX: Must set true on mount (StrictMode does mount→unmount→mount)
        isMountedRef.current = true;
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    const setQueueSync = useCallback((updater: (prev: PhotoQueueItem[]) => PhotoQueueItem[]) => {
        const prev = queueRef.current;
        const next = updater(prev);
        queueRef.current = next;

        console.log('[useFoodBatchAnalysis] setQueueSync:', {
            prevLength: prev.length,
            nextLength: next.length,
            isMounted: isMountedRef.current,
            statuses: next.map(p => `${p.id.slice(0, 4)}:${p.status}`).join(', '),
        });

        // P0 FIX: Always sync UI state - React 18 handles unmounted updates gracefully
        // The isMountedRef guard was preventing final SUCCESS updates from reaching FoodLogPage
        setPhotoQueue(next);
    }, []);

    const updatePhoto = useCallback(
        (id: string, patch: Partial<PhotoQueueItem>) => {
            if (cancelledRef.current) {
                console.log('[useFoodBatchAnalysis] updatePhoto BLOCKED by cancelled flag:', { id, patch });
                return;
            }
            console.log('[useFoodBatchAnalysis] updatePhoto:', { id: id.slice(0, 4), patch: Object.keys(patch) });
            setQueueSync((prev) => prev.map((p) => {
                if (p.id !== id) return p;
                // P1.2: Protect cancelled status from being overwritten by late results
                // This prevents race condition: cancel -> backend returns SUCCESS -> overwrite cancelled
                if (p.status === 'cancelled') {
                    console.log('[useFoodBatchAnalysis] updatePhoto BLOCKED - item already cancelled:', { id });
                    return p;
                }
                return { ...p, ...patch };
            }));
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
        async (controller: AbortController, runId: number) => {
            // P1.2: Check both abort and runId for stale batch detection
            while (!controller.signal.aborted && !cancelledRef.current && runId === runIdRef.current) {
                const next = getNextPending();
                if (!next) break;
                await processOne(next, controller);
                // P1.2: Check again after async operation in case batch was cancelled/restarted
                if (runId !== runIdRef.current) {
                    console.log('[processQueue] Stale runId detected, stopping processing');
                    break;
                }
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
            // P1.2: Increment runId to invalidate any stale promises from previous batch
            runIdRef.current += 1;
            const currentRunId = runIdRef.current;
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
                await processQueue(controller, currentRunId);
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
            // Only error or cancelled status is retryable
            if (!photo || (photo.status !== 'error' && photo.status !== 'cancelled')) return;
            // Block non-retryable error codes (e.g., daily limit)
            if (photo.errorCode && NON_RETRYABLE_ERROR_CODES.has(photo.errorCode)) return;

            // Just mark as pending, don't auto-start (multi-select mode)
            // IMPORTANT: Keep mealId and mealPhotoId for retry (prevents duplicate MealPhoto)
            setQueueSync((prev) =>
                prev.map((p) =>
                    // Allow retry for error OR cancelled
                    p.id === id && (p.status === 'error' || p.status === 'cancelled')
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

            // Mark all selected as pending with FULL RESET
            // P1.3: Reset all result fields but KEEP mealId/mealPhotoId for consistency
            const validIds = new Set(ids);

            setQueueSync((prev) =>
                prev.map((p) => {
                    if (!validIds.has(p.id)) return p;

                    // Allow retry for error AND cancelled
                    if (p.status !== 'error' && p.status !== 'cancelled') return p;

                    // Block non-retryable error codes
                    if (p.errorCode && NON_RETRYABLE_ERROR_CODES.has(p.errorCode)) return p;

                    return {
                        ...p,
                        status: 'pending' as PhotoUploadStatus,
                        // Clear ALL result/error fields
                        errorCode: undefined,
                        error: undefined,
                        result: undefined,
                        taskId: undefined,
                        // Clear any previous recognition data
                        // (TS might not complain if strict, but good to be explicit for runtime)
                    };
                })
            );

            // Determine if we have an existing meal_id from any SUCCESS item
            // P1.4: Strict Meal ID reuse
            // If there's already a success item, we MUST use its meal_id for the retries
            const existingSuccessItem = queueRef.current.find(p => p.status === 'success' && p.mealId);
            if (existingSuccessItem?.mealId) {
                console.log('[useFoodBatchAnalysis] Retry: Found existing mealId from success item:', existingSuccessItem.mealId);
                batchMealIdRef.current = existingSuccessItem.mealId;
            } else {
                console.log('[useFoodBatchAnalysis] Retry: No existing success mealId, will generate new if needed');
                // Don't clear batchMealIdRef.current here if it remembers context, 
                // but strictly speaking for a new "attempt" if all failed, we might want to start fresh 
                // OR keep the one from context. 
                // Current logic: recognizeFood uses item.mealId ?? batchMealIdRef.current.
            }

            // Start processing
            cancelledRef.current = false;
            processingRef.current = true;
            setIsProcessing(true);

            // P1.2: New run for retry -> Increment runId
            runIdRef.current += 1;
            const retryRunId = runIdRef.current;

            // New AbortController
            const controller = new AbortController();
            abortRef.current = controller;

            console.log(`[useFoodBatchAnalysis] Starting RETRY run #${retryRunId} for ${ids.length} items`);

            processQueue(controller, retryRunId).finally(() => {
                // Only unset if we are still the active run
                if (runIdRef.current === retryRunId) {
                    abortRef.current = null;
                    processingRef.current = false;
                    if (isMountedRef.current) setIsProcessing(false);
                }
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
        // P1.2: New run for manual start
        runIdRef.current += 1;
        const manualRunId = runIdRef.current;
        processingRef.current = true;
        setIsProcessing(true);

        const controller = new AbortController();
        abortRef.current = controller;

        processQueue(controller, manualRunId).finally(() => {
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

        // ============================================================
        // NEW: Send cancel event to backend (fire-and-forget)
        // ============================================================

        // Generate client_cancel_id for idempotency
        const clientCancelId = generateUUID();

        // Collect all identifiers from queue
        const taskIds: string[] = [];
        const mealPhotoIds: number[] = [];

        queueRef.current.forEach((p) => {
            // Collect task IDs that are in-flight
            if (p.taskId && isInFlightStatus(p.status)) {
                taskIds.push(p.taskId);
            }
            // Collect meal photo IDs (even if empty - backend needs to know)
            if (p.mealPhotoId) {
                mealPhotoIds.push(p.mealPhotoId);
            }
        });

        // Guard: Only send cancel event if there's something to cancel
        // User clicked Cancel, but always send event for audit trail (even if noop)
        const hasAnythingToCancel = taskIds.length > 0 || mealPhotoIds.length > 0 || batchMealIdRef.current !== undefined;

        if (hasAnythingToCancel) {
            // Build cancel payload
            const cancelPayload: CancelRequest = {
                client_cancel_id: clientCancelId,
                run_id: runIdRef.current,
                meal_id: batchMealIdRef.current ?? null,
                meal_photo_ids: mealPhotoIds.length > 0 ? mealPhotoIds : [],
                task_ids: taskIds.length > 0 ? taskIds : [],
                reason: 'user_cancel',
            };

            // Send cancel event (fire-and-forget, does not block UI)
            void cancelAiProcessing(cancelPayload);
            console.log('[cancelBatch] Cancel event sent. Backend will handle meal cleanup if needed.');
        } else {
            console.log('[cancelBatch] Nothing to cancel (empty queue), skipping cancel event.');
        }

        // ============================================================
        // Existing logic: Local cleanup (meal deletion removed - backend handles it)
        // ============================================================

        // P0: Cancel no longer deletes meal directly.
        // Backend will:
        // 1. Finalize meal status (FAILED if all photos failed/cancelled)
        // 2. Hide FAILED meals in API responses
        // 3. Delete orphan meals in background cleanup
        // This prevents race conditions where cancel arrives after meal deletion.

        setQueueSync((prev) =>
            prev.map((p) => {
                // P1.2: Keep terminal states as-is using unified helper
                if (isTerminalStatus(p.status)) return p;
                // P1: Use 'cancelled' status instead of 'error' for user cancellation
                return {
                    ...p,
                    status: 'cancelled' as const,
                    errorCode: AI_ERROR_CODES.CANCELLED,
                    error: getAiErrorMessage(AI_ERROR_CODES.CANCELLED),
                };
            })
        );

        // Old cancelAiTask calls - kept for backward compatibility
        // (cancelAiProcessing handles this better, but keeping as fallback)
        taskIds.forEach((taskId) => {
            void cancelAiTask(taskId);
        });

        processingRef.current = false;
        if (isMountedRef.current) setIsProcessing(false);
    }, [setQueueSync]);

    const cleanup = useCallback(() => {
        cancelledRef.current = true;
        abortRef.current?.abort();
        abortRef.current = null;

        // ============================================================
        // NEW: Send cancel event to backend (fire-and-forget)
        // ============================================================

        // Generate client_cancel_id for idempotency
        const clientCancelId = generateUUID();

        // Collect all identifiers from queue
        const taskIds: string[] = [];
        const mealPhotoIds: number[] = [];

        queueRef.current.forEach((p) => {
            // Collect task IDs that are not in terminal state
            if (p.taskId && !isTerminalStatus(p.status)) {
                taskIds.push(p.taskId);
            }
            // Collect meal photo IDs
            if (p.mealPhotoId) {
                mealPhotoIds.push(p.mealPhotoId);
            }
        });

        // Guard: Only send cancel event if there's something to cancel
        // Prevents spam CancelEvent on empty cleanup (e.g., modal close on empty queue)
        const hasAnythingToCancel = taskIds.length > 0 || mealPhotoIds.length > 0 || batchMealIdRef.current !== undefined;

        if (hasAnythingToCancel) {
            // Build cancel payload
            const cancelPayload: CancelRequest = {
                client_cancel_id: clientCancelId,
                run_id: runIdRef.current,
                meal_id: batchMealIdRef.current ?? null,
                meal_photo_ids: mealPhotoIds.length > 0 ? mealPhotoIds : [],
                task_ids: taskIds.length > 0 ? taskIds : [],
                reason: 'cleanup',
            };

            // Send cancel event (fire-and-forget, does not block UI)
            void cancelAiProcessing(cancelPayload);
            console.log('[cleanup] Cancel event sent. Backend will handle meal cleanup if needed.');
        } else {
            console.log('[cleanup] Nothing to cancel, skipping cancel event.');
        }

        // ============================================================
        // Existing logic: Cleanup (meal deletion removed - backend handles it)
        // ============================================================

        // P0: Cleanup no longer deletes meal directly.
        // Backend will handle orphan meal cleanup after finalization.
        // This prevents race conditions and simplifies frontend logic.

        // Old cancelAiTask calls - kept for backward compatibility
        taskIds.forEach((taskId) => {
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
