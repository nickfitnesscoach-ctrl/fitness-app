/**
 * AI API Module Exports
 */

// API functions
export { recognizeFood, getTaskStatus, mapToAnalysisResult } from './ai.api';

// Types
export type {
    // Request
    MealType,
    RecognizeRequest,
    // Response (API format)
    ApiRecognizedItem,
    RecognitionTotals,
    RecognizeResponse,
    TaskState,
    TaskStatus,
    TaskSuccessResult,
    TaskStatusResponse,
    // UI format (mapped)
    RecognizedItem,
    AnalysisResult,
    BatchResult,
} from './ai.types';
