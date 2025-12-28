/**
 * AI API Module Exports
 */

// API functions
export { recognizeFood, getTaskStatus, cancelAiTask, mapToAnalysisResult } from './ai.api';

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
    TaskResult,
    TaskStatusResponse,
    // UI format (mapped)
    RecognizedItem,
    AnalysisResult,
    BatchResult,
} from './ai.types';
