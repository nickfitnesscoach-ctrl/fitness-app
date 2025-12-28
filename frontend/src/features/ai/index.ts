/**
 * AI Feature Module
 * 
 * Food photo recognition and analysis for EatFit24.
 * Aligned with API Contract: /docs/API_CONTRACT_AI_AND_TELEGRAM.md
 * 
 * @module features/ai
 */

// ============================================================
// API Layer
// ============================================================

export {
    recognizeFood,
    getTaskStatus,
    mapToAnalysisResult
} from './api';

export type {
    // Request types
    MealType,
    RecognizeRequest,
    // API response types
    ApiRecognizedItem,
    RecognitionTotals,
    RecognizeResponse,
    TaskState,
    TaskStatus,
    TaskResult,
    TaskStatusResponse,
    // UI types (mapped from API)
    RecognizedItem,
    AnalysisResult,
    BatchResult,
} from './api';

// ============================================================
// Hooks
// ============================================================

export {
    useTaskPolling,
    useFoodBatchAnalysis
} from './hooks';

export type { PollingStatus } from './hooks';

// ============================================================
// Model (Types & Constants)
// ============================================================

export type {
    FileWithComment,
    BatchProgress,
    BatchAnalysisOptions
} from './model';

export {
    POLLING_CONFIG,
    MEAL_TYPES,
    MEAL_TYPE_OPTIONS,
    AI_ERROR_CODES,
    AI_ERROR_MESSAGES,
    AI_LIMITS,
    NON_RETRYABLE_ERROR_CODES,
    getAiErrorMessage,
} from './model';

export type { AiErrorCode } from './model';

// ============================================================
// Lib (Utilities)
// ============================================================

export {
    isHeicFile,
    convertHeicToJpeg,
    processFilesForUpload,
    createPreviewUrl,
    validateFileSize,
    getFileExtension,
    isImageFile,
} from './lib';

// ============================================================
// UI Components
// ============================================================

export {
    // Upload
    SelectedPhotosList,
    UploadDropzone,
    // Result
    BatchResultsModal,
    // States
    BatchProcessingScreen,
    LimitReachedModal,
} from './ui';
