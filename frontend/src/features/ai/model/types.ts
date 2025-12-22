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

/** Progress state for batch processing */
export interface BatchProgress {
    current: number;
    total: number;
}

/** Options for batch analysis hook */
export interface BatchAnalysisOptions {
    onDailyLimitReached?: () => void;
    getDateString: () => string;
    getMealType: () => string;
}
