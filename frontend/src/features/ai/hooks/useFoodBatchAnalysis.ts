/**
 * Hook for managing batch food photo analysis
 * Handles file processing, polling, fallbacks, and error handling
 * 
 * Aligned with API Contract:
 * - Uses user_comment (not description)
 * - Uses lowercase meal_type
 * - Maps items/amount_grams from API response
 */

import { useState, useRef } from 'react';
import { recognizeFood, getTaskStatus, mapToAnalysisResult } from '../api';
import type { AnalysisResult, BatchResult, TaskStatusResponse } from '../api';
import type { FileWithComment, BatchAnalysisOptions } from '../model';
import { POLLING_CONFIG, AI_ERROR_CODES, getAiErrorMessage } from '../model';
import { convertHeicToJpeg } from '../lib';
import { api } from '../../../services/api';

interface UseFoodBatchAnalysisResult {
    isProcessing: boolean;
    progress: { current: number; total: number };
    results: BatchResult[];
    error: string | null;
    startBatch: (files: FileWithComment[]) => Promise<void>;
    cancelBatch: () => void;
}

/**
 * Hook for managing batch food photo analysis
 */
export const useFoodBatchAnalysis = (
    options: BatchAnalysisOptions
): UseFoodBatchAnalysisResult => {
    const [isProcessing, setIsProcessing] = useState(false);
    const [progress, setProgress] = useState({ current: 0, total: 0 });
    const [results, setResults] = useState<BatchResult[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [cancelRequested, setCancelRequested] = useState(false);

    // For async polling cancellation
    const pollingAbortRef = useRef<AbortController | null>(null);

    /**
     * Poll task status until completion or timeout
     */
    const pollTaskStatus = async (
        taskId: string,
        mealId: number,
        abortController: AbortController
    ): Promise<AnalysisResult | null> => {
        const startTime = Date.now();
        let attempt = 0;

        while (!abortController.signal.aborted) {
            const elapsed = Date.now() - startTime;
            if (elapsed >= POLLING_CONFIG.CLIENT_TIMEOUT_MS) {
                const timeoutError = new Error('Превышено время ожидания распознавания');
                (timeoutError as any).errorType = AI_ERROR_CODES.TASK_TIMEOUT;
                throw timeoutError;
            }

            const delay = Math.min(
                POLLING_CONFIG.INITIAL_DELAY_MS * Math.pow(POLLING_CONFIG.BACKOFF_MULTIPLIER, attempt),
                POLLING_CONFIG.MAX_DELAY_MS
            );

            try {
                const taskStatus: TaskStatusResponse = await getTaskStatus(taskId);
                console.log(`[Polling] Task ${taskId}: state=${taskStatus.state}, status=${taskStatus.status}`);

                // SUCCESS
                if (taskStatus.state === 'SUCCESS' && taskStatus.status === 'success') {
                    let analysisResult = mapToAnalysisResult(taskStatus.result, mealId);

                    // Fallback: if empty items but meal_id exists, try fetching from meal API
                    if ((!analysisResult || analysisResult.recognized_items.length === 0) && mealId) {
                        console.log(`[Polling] Empty items but meal_id=${mealId}, trying fallback...`);

                        for (let fAttempt = 1; fAttempt <= 3; fAttempt++) {
                            const delayMs = fAttempt * 1000;
                            await new Promise(resolve => setTimeout(resolve, delayMs));

                            try {
                                const mealData = await api.getMealAnalysis(mealId);
                                if (mealData.recognized_items && mealData.recognized_items.length > 0) {
                                    console.log(`[Polling] Fallback SUCCESS: found ${mealData.recognized_items.length} items`);

                                    // Map meal data to AnalysisResult format
                                    analysisResult = {
                                        meal_id: mealId,
                                        recognized_items: mealData.recognized_items.map(item => ({
                                            id: String(item.id),
                                            name: item.name,
                                            grams: item.grams,
                                            calories: item.calories,
                                            protein: item.protein,
                                            fat: item.fat,
                                            carbohydrates: item.carbohydrates,
                                        })),
                                        total_calories: mealData.recognized_items.reduce((sum, i) => sum + (i.calories || 0), 0),
                                        total_protein: mealData.recognized_items.reduce((sum, i) => sum + (i.protein || 0), 0),
                                        total_fat: mealData.recognized_items.reduce((sum, i) => sum + (i.fat || 0), 0),
                                        total_carbohydrates: mealData.recognized_items.reduce((sum, i) => sum + (i.carbohydrates || 0), 0),
                                    };
                                    break;
                                }
                            } catch (fallbackErr) {
                                console.warn(`[Polling] Fallback attempt ${fAttempt} failed:`, fallbackErr);
                                const errMsg = (fallbackErr as Error)?.message || '';
                                if (errMsg.includes('404')) break;
                            }
                        }
                    }

                    // If still empty but has meal_id, return with neutral message
                    if ((!analysisResult || analysisResult.recognized_items.length === 0) && mealId) {
                        return {
                            meal_id: mealId,
                            recognized_items: [],
                            total_calories: 0,
                            total_protein: 0,
                            total_fat: 0,
                            total_carbohydrates: 0,
                            _neutralMessage: 'Анализ завершён, проверьте дневник',
                        };
                    }

                    // No meal_id and no items = failure
                    if (!analysisResult || analysisResult.recognized_items.length === 0) {
                        const emptyError = new Error('Ошибка обработки');
                        (emptyError as any).errorType = AI_ERROR_CODES.EMPTY_RESULT;
                        throw emptyError;
                    }

                    return analysisResult;
                }

                // FAILURE
                if (taskStatus.state === 'FAILURE' || taskStatus.status === 'failed') {
                    const failError = new Error(taskStatus.error || 'Ошибка обработки фото');
                    (failError as any).errorType = AI_ERROR_CODES.TASK_FAILURE;
                    throw failError;
                }

                // Still processing - wait and retry
                await new Promise(resolve => setTimeout(resolve, delay));
                attempt++;

            } catch (err: any) {
                if (abortController.signal.aborted) return null;

                // Rethrow known error types
                if (err.errorType) throw err;

                // Network error - retry a few times
                if (attempt < 3) {
                    await new Promise(resolve => setTimeout(resolve, delay));
                    attempt++;
                    continue;
                }

                const networkError = new Error('Ошибка сети при получении результата');
                (networkError as any).errorType = AI_ERROR_CODES.NETWORK_ERROR;
                throw networkError;
            }
        }

        return null; // Aborted
    };

    /**
     * Start processing a batch of files
     */
    const startBatch = async (filesWithComments: FileWithComment[]): Promise<void> => {
        setIsProcessing(true);
        setProgress({ current: 0, total: filesWithComments.length });
        setResults([]);
        setError(null);
        setCancelRequested(false);

        const abortController = new AbortController();
        pollingAbortRef.current = abortController;

        const batchResults: BatchResult[] = [];

        try {
            for (let i = 0; i < filesWithComments.length; i++) {
                if (cancelRequested || abortController.signal.aborted) {
                    console.log('[Batch] User cancelled processing');
                    break;
                }

                const { file, comment } = filesWithComments[i];
                setProgress({ current: i + 1, total: filesWithComments.length });

                try {
                    // Convert HEIC/HEIF to JPEG before upload
                    const processedFile = await convertHeicToJpeg(file);

                    // Get date and meal type from options
                    const dateStr = options.getDateString();
                    const mealTypeValue = options.getMealType().toLowerCase(); // Ensure lowercase

                    // Call recognize with API contract field names
                    const recognizeResponse = await recognizeFood(
                        processedFile,
                        comment,                    // user_comment
                        mealTypeValue,              // lowercase meal_type
                        dateStr
                    );

                    // Poll for result
                    const result = await pollTaskStatus(
                        recognizeResponse.task_id,
                        recognizeResponse.meal_id,
                        abortController
                    );

                    if (!result) {
                        // Cancelled
                        break;
                    }

                    // Check if we have valid result
                    if (result.meal_id || (result.recognized_items && result.recognized_items.length > 0)) {
                        batchResults.push({
                            file,
                            status: 'success',
                            data: result,
                        });
                    } else {
                        batchResults.push({
                            file,
                            status: 'error',
                            error: 'Ошибка обработки. Попробуйте ещё раз.',
                        });
                    }

                } catch (err: any) {
                    console.error(`[Batch] Error processing file ${file.name}:`, err);

                    // Check for daily limit
                    if (err.code === AI_ERROR_CODES.DAILY_LIMIT_REACHED ||
                        err.error === AI_ERROR_CODES.DAILY_LIMIT_REACHED) {
                        options.onDailyLimitReached?.();
                        batchResults.push({
                            file,
                            status: 'error',
                            error: getAiErrorMessage(AI_ERROR_CODES.DAILY_LIMIT_REACHED),
                        });
                        break;
                    }

                    // Get localized error message
                    const errorMessage = getAiErrorMessage(err.errorType || err.error || err.message);
                    batchResults.push({
                        file,
                        status: 'error',
                        error: errorMessage,
                    });
                }
            }

            setResults(batchResults);

        } catch (err: any) {
            console.error('[Batch] Global error:', err);
            setError('Произошла ошибка при обработке фотографий.');
        } finally {
            setIsProcessing(false);
            pollingAbortRef.current = null;
        }
    };

    /**
     * Cancel the current batch processing
     */
    const cancelBatch = (): void => {
        setCancelRequested(true);
        if (pollingAbortRef.current) {
            pollingAbortRef.current.abort();
        }
        setIsProcessing(false);
    };

    return {
        isProcessing,
        progress,
        results,
        error,
        startBatch,
        cancelBatch,
    };
};
