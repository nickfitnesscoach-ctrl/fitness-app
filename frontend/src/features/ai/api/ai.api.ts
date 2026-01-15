import { fetchWithTimeout, getHeaders, getHeadersWithoutContentType, log } from '../../../services/api/client';
import { URLS } from '../../../services/api/urls';
import type {
    RecognizeResponse,
    TaskStatusResponse,
    AnalysisResult,
    RecognizedItem,
    ApiRecognizedItem,
    RecognitionTotals,
    MealType,
    CancelRequest,
    CancelResponse,
} from './ai.types';

// ============================================================
// Helpers
// ============================================================

const MEAL_TYPE_MAP: Record<string, string> = {
    'завтрак': 'BREAKFAST',
    'breakfast': 'BREAKFAST',
    'обед': 'LUNCH',
    'lunch': 'LUNCH',
    'ужин': 'DINNER',
    'dinner': 'DINNER',
    'перекус': 'SNACK',
    'snack': 'SNACK',
    'BREAKFAST': 'BREAKFAST',
    'LUNCH': 'LUNCH',
    'DINNER': 'DINNER',
    'SNACK': 'SNACK',
};

const mapMealTypeToApi = (mealType?: MealType | string): string | undefined => {
    if (!mealType) return undefined;
    const normalized = String(mealType).trim();
    const lower = normalized.toLowerCase();
    return MEAL_TYPE_MAP[lower] || MEAL_TYPE_MAP[normalized] || 'SNACK';
};

const safeJson = async (res: Response) => {
    try {
        return await res.json();
    } catch {
        return {};
    }
};

// ============================================================
// API calls
// ============================================================

/**
 * Start food recognition for an image.
 *
 * Multi-Photo Meal Support:
 * - Pass meal_id to add photo to existing meal
 * - If not provided, backend will find/create draft meal within 10-min window
 * - Returns meal_id for subsequent photos in the same batch
 *
 * Retry Support:
 * - Pass meal_photo_id to retry existing failed photo (no duplicate created)
 */
export const recognizeFood = async (
    imageFile: File,
    userComment?: string,
    mealType?: MealType | string,
    date?: string,
    signal?: AbortSignal,
    mealId?: number, // Optional: for multi-photo meals
    mealPhotoId?: number // Optional: for retry (re-use existing MealPhoto)
): Promise<RecognizeResponse> => {
    log(`AI recognize: ${imageFile.name}${mealId ? ` (meal_id=${mealId})` : ''}${mealPhotoId ? ` (retry photo_id=${mealPhotoId})` : ''}`);

    const formData = new FormData();
    formData.append('image', imageFile);

    if (userComment) formData.append('user_comment', userComment);

    const apiMealType = mapMealTypeToApi(mealType);
    if (apiMealType) formData.append('meal_type', apiMealType);

    if (date) formData.append('date', date);

    // Multi-photo grouping: pass meal_id to attach to existing meal
    if (mealId) formData.append('meal_id', String(mealId));

    // Retry: pass meal_photo_id to re-use existing photo record
    if (mealPhotoId) formData.append('meal_photo_id', String(mealPhotoId));

    const response = await fetchWithTimeout(
        URLS.recognize,
        {
            method: 'POST',
            headers: getHeadersWithoutContentType(),
            body: formData,
            signal,
        },
        undefined,
        false,
        signal
    );

    const requestId = response.headers.get('X-Request-ID');
    if (requestId) log(`X-Request-ID: ${requestId}`);

    // 429 daily limit
    if (response.status === 429) {
        const data = await safeJson(response);
        const err = new Error(data.message || data.detail || 'Слишком много запросов');
        (err as any).code = data.error === 'DAILY_PHOTO_LIMIT_EXCEEDED' ? 'DAILY_LIMIT_REACHED' : 'THROTTLED';
        (err as any).data = data;
        throw err;
    }

    if (response.status !== 202) {
        const data = await safeJson(response);
        throw new Error(data.message || data.detail || 'Ошибка запуска распознавания');
    }

    return (await safeJson(response)) as RecognizeResponse;
};

export const getTaskStatus = async (taskId: string, signal?: AbortSignal): Promise<TaskStatusResponse> => {
    log(`Get task status: ${taskId}`);

    const res = await fetch(`${URLS.taskStatus(taskId)}`, {
        method: 'GET',
        headers: getHeaders(),
        signal,
    });

    if (res.status === 404) {
        throw new Error('Задача не найдена или доступ запрещен');
    }

    if (!res.ok) {
        const data = await safeJson(res);
        throw new Error(data.message || 'Ошибка при получении статуса');
    }

    const data = (await safeJson(res)) as TaskStatusResponse;

    // Debug logging: show actual status values from backend
    log(`Task ${taskId} status: state=${data.state}, status=${data.status}`);

    return data;
};

/**
 * Cancel an AI task on the backend (fire-and-forget)
 * Called when user cancels batch - prevents meal creation
 *
 * @deprecated Use cancelAiProcessing for batch cancellation
 */
export const cancelAiTask = async (taskId: string): Promise<void> => {
    log(`Cancel AI task: ${taskId}`);
    try {
        await fetch(`${URLS.cancelTask(taskId)}`, {
            method: 'POST',
            headers: getHeaders(),
        });
    } catch (err) {
        // Fire-and-forget: don't throw on network errors
        console.warn('[cancelAiTask] Failed to cancel', taskId, err);
    }
};

/**
 * Cancel AI batch processing on the backend (fire-and-forget)
 *
 * Sends structured cancel event with all available identifiers:
 * - client_cancel_id: UUID for idempotency
 * - run_id: Frontend batch run identifier
 * - meal_id: Meal to mark as cancelled
 * - meal_photo_ids: Photos to mark as CANCELLED
 * - task_ids: Celery tasks to revoke
 * - reason: Why the cancel happened
 *
 * This is fire-and-forget - errors are logged but NOT thrown.
 * UI should not wait for this call to complete.
 *
 * @param payload Cancel request payload
 * @param signal Optional AbortSignal (for cleanup, not for blocking UI)
 */
export const cancelAiProcessing = async (
    payload: CancelRequest,
    signal?: AbortSignal
): Promise<void> => {
    // Silent logging - only in verbose mode
    const LOG_VERBOSE = false; // Can be controlled by env var if needed

    if (LOG_VERBOSE) {
        console.debug('[cancelAiProcessing] Sending cancel event:', {
            client_cancel_id: payload.client_cancel_id,
            run_id: payload.run_id,
            meal_id: payload.meal_id,
            photo_count: payload.meal_photo_ids?.length ?? 0,
            task_count: payload.task_ids?.length ?? 0,
            reason: payload.reason,
        });
    }

    try {
        const response = await fetch(URLS.cancelBatch, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(payload),
            signal,
        });

        if (LOG_VERBOSE && response.ok) {
            const data: CancelResponse = await response.json();
            console.debug('[cancelAiProcessing] Cancel acknowledged:', {
                cancelled_tasks: data.cancelled_tasks,
                updated_photos: data.updated_photos,
                noop: data.noop,
            });
        }
    } catch (err: any) {
        // Fire-and-forget: suppress all errors
        // Only log if verbose mode is enabled or if it's NOT an abort
        if (LOG_VERBOSE && err?.name !== 'AbortError') {
            console.debug('[cancelAiProcessing] Cancel request failed (non-critical):', err.message);
        }
    }
};

// ============================================================
// Mapping
// ============================================================

const normalizeTotals = (totals: any): RecognitionTotals => {
    const t = totals || {};
    return {
        calories: Number(t.calories ?? 0) || 0,
        protein: Number(t.protein ?? 0) || 0,
        fat: Number(t.fat ?? 0) || 0,
        carbohydrates: Number(t.carbohydrates ?? 0) || 0,
    };
};

const mapItem = (apiItem: ApiRecognizedItem): RecognizedItem => ({
    id: crypto.randomUUID(),
    name: String(apiItem.name || 'Unknown'),
    grams: Number(apiItem.amount_grams ?? 0) || 0,
    calories: Number(apiItem.calories ?? 0) || 0,
    protein: Number(apiItem.protein ?? 0) || 0,
    fat: Number(apiItem.fat ?? 0) || 0,
    carbohydrates: Number(apiItem.carbohydrates ?? 0) || 0,
    confidence: apiItem.confidence ?? null,
});

export const mapToAnalysisResult = (taskStatus: TaskStatusResponse): AnalysisResult | null => {
    if (taskStatus.status !== 'success' || taskStatus.state !== 'SUCCESS') return null;

    const result = taskStatus.result;
    if (!result) return null;

    // Логическая ошибка с бэка
    if (result.error) return null;

    const items = Array.isArray(result.items) ? result.items : [];
    if (items.length === 0) return null;

    const totals = normalizeTotals(result.totals);

    return {
        meal_id: result.meal_id,
        recognized_items: items.map(mapItem),
        total_calories: totals.calories,
        total_protein: totals.protein,
        total_fat: totals.fat,
        total_carbohydrates: totals.carbohydrates,
    };
};
