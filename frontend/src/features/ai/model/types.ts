/**
 * AI Feature Model Types
 */

// ============================================================
// File Upload Types
// ============================================================

/**
 * File with associated comment and preview URL
 * Used for food photo uploads with individual comments per photo
 */
export interface FileWithComment {
    file: File;
    comment: string;
    previewUrl?: string; // For HEIC preview support
}

// ============================================================
// Processing State Types
// ============================================================

/**
 * Status of individual photo in upload queue (6 states)
 */
export type PhotoUploadStatus =
    | 'pending'      // Ожидает в очереди
    | 'compressing'  // Сжимаю фото…
    | 'uploading'    // Загружаю…
    | 'processing'   // В обработке…
    | 'success'      // Готово ✅
    | 'error';       // Ошибка

/**
 * Extended state for individual photo in queue
 * id must be stable for retry button and list rendering
 */
export interface PhotoQueueItem {
    /** Unique stable ID for React key and retry */
    id: string;
    /** Original file */
    file: File;
    /** User comment for this photo */
    comment: string;
    /** Preview URL (set immediately at start, before compressing) */
    previewUrl?: string;
    /** Current processing status */
    status: PhotoUploadStatus;
    /** Error code for programmatic checks (e.g., AI_ERROR_CODES.CANCELLED) */
    errorCode?: string;
    /** Error message for display if status === 'error' */
    error?: string;
    /** Analysis result if status === 'success' */
    result?: import('../api').AnalysisResult;
    /** Task ID from backend (set after POST /recognize/) */
    taskId?: string;
    /** Meal ID from backend */
    mealId?: number;
}

/** Progress state for batch processing */
export interface BatchProgress {
    current: number;
    total: number;
}

/** Options for batch analysis hook */
export interface BatchAnalysisOptions {
    onDailyLimitReached?: () => void;
}
