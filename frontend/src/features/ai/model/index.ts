/**
 * AI Feature Model Exports
 */

// Types
export type {
    FileWithComment,
    BatchProgress,
    BatchAnalysisOptions,
    PhotoUploadStatus,
    PhotoQueueItem,
} from './types';

// Constants
export {
    POLLING_CONFIG,
    PHOTO_STATUS_LABELS,
    MEAL_TYPES,
    MEAL_TYPE_OPTIONS,
    AI_ERROR_CODES,
    AI_ERROR_MESSAGES,
    AI_LIMITS,
    NON_RETRYABLE_ERROR_CODES,
    getAiErrorMessage,
} from './constants';
export type { AiErrorCode } from './constants';
