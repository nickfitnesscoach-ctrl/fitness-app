/**
 * Image utilities for handling various image formats
 * F-007 FIX: HEIC/HEIF support for iOS photos
 */

import heic2any from 'heic2any';

/**
 * Check if file is HEIC/HEIF format (common on iOS)
 */
export const isHeicFile = (file: File): boolean => {
    const extension = file.name.toLowerCase().split('.').pop();
    return extension === 'heic' || extension === 'heif' || 
           file.type === 'image/heic' || file.type === 'image/heif';
};

/**
 * Convert HEIC/HEIF file to JPEG
 * Returns original file if not HEIC or conversion fails
 */
export const convertHeicToJpeg = async (file: File): Promise<File> => {
    if (!isHeicFile(file)) {
        return file;
    }

    console.log(`[ImageUtils] Converting HEIC file: ${file.name}`);

    try {
        const blob = await heic2any({
            blob: file,
            toType: 'image/jpeg',
            quality: 0.9
        });

        // heic2any can return array of blobs for multi-image HEIC
        const resultBlob = Array.isArray(blob) ? blob[0] : blob;
        
        // Create new File with .jpg extension
        const newFileName = file.name.replace(/\.(heic|heif)$/i, '.jpg');
        const convertedFile = new File([resultBlob], newFileName, { type: 'image/jpeg' });
        
        console.log(`[ImageUtils] Converted ${file.name} to ${newFileName} (${convertedFile.size} bytes)`);
        return convertedFile;
    } catch (error) {
        console.error(`[ImageUtils] Failed to convert HEIC file ${file.name}:`, error);
        // Return original file - backend might handle it or show error
        return file;
    }
};

/**
 * Process multiple files, converting HEIC to JPEG
 */
export const processFilesForUpload = async (files: File[]): Promise<File[]> => {
    const processedFiles: File[] = [];
    
    for (const file of files) {
        const processed = await convertHeicToJpeg(file);
        processedFiles.push(processed);
    }
    
    return processedFiles;
};

/**
 * Create preview URL for file (handles HEIC conversion for preview)
 */
export const createPreviewUrl = async (file: File): Promise<string> => {
    if (isHeicFile(file)) {
        try {
            const convertedFile = await convertHeicToJpeg(file);
            return URL.createObjectURL(convertedFile);
        } catch (error) {
            console.error('[ImageUtils] Failed to create preview for HEIC:', error);
            // Return empty or placeholder
            return '';
        }
    }
    return URL.createObjectURL(file);
};
