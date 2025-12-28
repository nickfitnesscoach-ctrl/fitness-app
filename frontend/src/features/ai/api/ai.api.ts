import { fetchWithTimeout, getHeadersWithoutContentType, log } from '../../../services/api/client';
import { URLS } from '../../../services/api/urls';
import type {
    RecognizeResponse,
    TaskStatusResponse,
    AnalysisResult,
    RecognizedItem,
    ApiRecognizedItem,
    RecognitionTotals,
    MealType,
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

const getAuthHeaders = () => {
    const initData = (window as any).Telegram?.WebApp?.initData || '';
    return {
        Authorization: `Bearer ${initData}`,
        'X-Telegram-Init-Data': initData,
    };
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

export const recognizeFood = async (
    imageFile: File,
    userComment?: string,
    mealType?: MealType | string,
    date?: string,
    signal?: AbortSignal
): Promise<RecognizeResponse> => {
    log(`AI recognize: ${imageFile.name}`);

    const formData = new FormData();
    formData.append('image', imageFile);

    if (userComment) formData.append('user_comment', userComment);

    const apiMealType = mapMealTypeToApi(mealType);
    if (apiMealType) formData.append('meal_type', apiMealType);

    if (date) formData.append('date', date);

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
        headers: {
            ...getAuthHeaders(),
            'Content-Type': 'application/json',
        },
        signal,
    });

    if (res.status === 404) {
        throw new Error('Задача не найдена или доступ запрещен');
    }

    if (!res.ok) {
        const data = await safeJson(res);
        throw new Error(data.message || 'Ошибка при получении статуса');
    }

    return (await safeJson(res)) as TaskStatusResponse;
};

/**
 * Cancel an AI task on the backend (fire-and-forget)
 * Called when user cancels batch - prevents meal creation
 */
export const cancelAiTask = async (taskId: string): Promise<void> => {
    log(`Cancel AI task: ${taskId}`);
    try {
        await fetch(`${URLS.cancelTask(taskId)}`, {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json',
            },
        });
    } catch (err) {
        // Fire-and-forget: don't throw on network errors
        console.warn('[cancelAiTask] Failed to cancel', taskId, err);
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
