/**
 * AI Recognition API Types
 * Aligned with backend:
 * - POST /api/v1/ai/recognize/ -> 202 { task_id, meal_id, meal_photo_id, status: "processing" }
 * - GET  /api/v1/ai/task/<id>/ -> 200 { task_id, status, state, result? , error? }
 *
 * Multi-Photo Meal Support:
 * - meal_id is always returned (created upfront in view)
 * - meal_photo_id tracks individual photo within a meal
 * - Subsequent photos can pass meal_id to group into same meal
 */

export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack';

export interface RecognizeRequest {
    image: File;
    meal_type: MealType;
    date?: string; // YYYY-MM-DD
    user_comment?: string;
    meal_id?: number; // Optional: for multi-photo meals
}

export interface ApiRecognizedItem {
    name: string;
    amount_grams: number;
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
    confidence?: number | null;
}

export interface RecognitionTotals {
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

export interface RecognizeResponse {
    task_id: string;
    meal_id: number; // Always returned now (created upfront)
    meal_photo_id: number; // Individual photo ID within the meal
    status: 'processing';
}

export type TaskState = 'PENDING' | 'STARTED' | 'RETRY' | 'SUCCESS' | 'FAILURE';
export type TaskStatus = 'processing' | 'success' | 'failed';

// SSOT: Normalized task status for frontend UI
export type NormalizedTaskStatus = 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'FAILED';

/**
 * Normalize task status from backend response to unified frontend enum.
 * Backend can return:
 * - state: 'PENDING' | 'STARTED' | 'RETRY' | 'SUCCESS' | 'FAILURE' (Celery states)
 * - status: 'processing' | 'success' | 'failed' (lowercase)
 *
 * This helper ensures consistent status checking across the frontend.
 */
export function normalizeTaskStatus(data: { state?: TaskState; status?: TaskStatus }): NormalizedTaskStatus {
    const state = String(data?.state ?? '').toUpperCase();
    const status = String(data?.status ?? '').toUpperCase();

    // Terminal states (order matters: check SUCCESS before PROCESSING)
    if (state === 'SUCCESS' || status === 'SUCCESS') return 'SUCCESS';
    if (state === 'FAILURE' || state === 'FAILED' || status === 'FAILED') return 'FAILED';

    // Processing states
    if (state === 'STARTED' || state === 'RETRY' || status === 'PROCESSING') return 'PROCESSING';

    // Default: pending
    return 'PENDING';
}

export interface TaskResult {
    meal_id: number | null;
    meal_photo_id?: number; // Photo ID for multi-photo tracking
    items: ApiRecognizedItem[];
    totals: Partial<RecognitionTotals> | {}; // backend гарантирует объект, но может быть пустой
    error?: string;
    error_message?: string;
    error_code?: string; // Structured error code from backend (UPSTREAM_TIMEOUT, INVALID_IMAGE, etc.)
    meta?: Record<string, any>;
    total_calories?: number; // иногда приходит
}

export interface TaskStatusResponse {
    task_id: string;
    status: TaskStatus;
    state: TaskState;
    result?: TaskResult;
    error?: string;
}

// =====================
// UI types
// =====================

export interface RecognizedItem {
    id: string;
    name: string;
    grams: number;
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
    confidence?: number | null;
}

export interface AnalysisResult {
    meal_id: number | string | null;
    recognized_items: RecognizedItem[];
    total_calories: number;
    total_protein: number;
    total_fat: number;
    total_carbohydrates: number;
    photo_url?: string;
}

export interface BatchResult {
    file: File;
    status: 'success' | 'error';
    data?: AnalysisResult;
    error?: string;
}
