/**
 * AI Feature Lib Exports
 */

export {
    isHeicFile,
    convertHeicToJpeg,
    processFilesForUpload,
    createPreviewUrl,
    validateFileSize,
    getFileExtension,
    isImageFile,
} from './image';

export {
    preprocessImage,
    preprocessFiles,
    PreprocessError,
    PREPROCESS_CONFIG,
    PREPROCESS_ERROR_CODES,
    type PreprocessResult,
    type PreprocessMetrics,
    type PreprocessErrorCode,
} from './imagePreprocess';

export { generateUUID } from './uuid';
