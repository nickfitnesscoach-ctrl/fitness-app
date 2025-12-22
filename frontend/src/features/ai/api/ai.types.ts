/**
 * AI Recognition API Types
 * 
 * Aligned with API Contract: /docs/API_CONTRACT_AI_AND_TELEGRAM.md
 * 
 * Endpoints:
 * - POST /api/v1/ai/recognize/ - Start recognition (returns 202)
 * - GET /api/v1/ai/task/<id>/ - Poll task status
 */

// ============================================================
// Request Types
// ============================================================

/** Meal type values (lowercase per API contract) */
export type MealType = 'breakfast' | 'lunch' | 'dinner' | 'snack';

/** Fields for POST /api/v1/ai/recognize/ */
export interface RecognizeRequest {
    image: File;
    meal_type: MealType;
    date: string; // YYYY-MM-DD
    user_comment?: string; // API uses user_comment (not description)
}

// ============================================================
// Response Types (aligned with API Contract)
// ============================================================

/** 
 * Item from task result
 * API uses amount_grams, we map to grams for UI
 */
export interface ApiRecognizedItem {
    name: string;
    amount_grams: number;  // API field name
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

/** Totals from task result */
export interface RecognitionTotals {
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

/** Response from POST /api/v1/ai/recognize/ (202 Accepted) */
export interface RecognizeResponse {
    task_id: string;
    meal_id: number;
    status: 'processing';
}

/** Task states from Celery */
export type TaskState = 'PENDING' | 'STARTED' | 'RETRY' | 'SUCCESS' | 'FAILURE';

/** Task status values */
export type TaskStatus = 'processing' | 'success' | 'failed';

/** Task result when success */
export interface TaskSuccessResult {
    meal_id: number;
    items: ApiRecognizedItem[];  // API uses "items", NOT "recognized_items"
    totals: RecognitionTotals;
}

/** GET /api/v1/ai/task/<id>/ response */
export interface TaskStatusResponse {
    task_id: string;
    status: TaskStatus;
    state: TaskState;
    result?: TaskSuccessResult;
    error?: string;
}

// ============================================================
// UI Types (for display, mapped from API)
// ============================================================

/** 
 * Display item for UI components
 * Uses "grams" for backward compatibility with existing UI
 */
export interface RecognizedItem {
    id?: string;
    name: string;
    grams: number;      // Mapped from API's amount_grams
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
    confidence?: number;
}

/** Analysis result for UI components */
export interface AnalysisResult {
    meal_id: number | string;
    recognized_items: RecognizedItem[];  // UI uses recognized_items for compat
    total_calories: number;
    total_protein: number;
    total_fat: number;
    total_carbohydrates: number;
    photo_url?: string;
    _neutralMessage?: string; // UI hotfix message
}

/** Batch result for multiple photo processing */
export interface BatchResult {
    file: File;
    status: 'success' | 'error';
    data?: AnalysisResult;
    error?: string;
}
