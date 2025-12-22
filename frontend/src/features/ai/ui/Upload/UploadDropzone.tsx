import React, { useRef, useState, useCallback } from 'react';
import { Camera, Upload } from 'lucide-react';

interface UploadDropzoneProps {
    onFilesSelected: (files: File[]) => void;
    maxFiles?: number;
    isDesktop?: boolean;
    disabled?: boolean;
}

/**
 * Upload dropzone component with desktop drag&drop support
 * Mobile: camera/file picker
 * Desktop: drag&drop + file picker
 */
export const UploadDropzone: React.FC<UploadDropzoneProps> = ({
    onFilesSelected,
    maxFiles = 5,
    isDesktop = false,
    disabled = false,
}) => {
    const [isDragOver, setIsDragOver] = useState(false);
    const inputRef = useRef<HTMLInputElement>(null);

    const handleFiles = useCallback((files: FileList | File[]) => {
        const fileList = Array.from(files);

        // Filter valid images
        const imageFiles = fileList.filter(file =>
            file.type.startsWith('image/') ||
            file.name.toLowerCase().endsWith('.heic') ||
            file.name.toLowerCase().endsWith('.heif')
        );

        if (imageFiles.length === 0) {
            alert('Пожалуйста, выберите изображения');
            return;
        }

        // Limit number of files
        if (imageFiles.length > maxFiles) {
            alert(`За один раз можно загрузить не более ${maxFiles} фото. Лишние будут проигнорированы.`);
        }

        // Filter by size (10MB max)
        const validFiles = imageFiles.slice(0, maxFiles).filter(file => {
            if (file.size > 10 * 1024 * 1024) {
                console.warn(`File ${file.name} is too large (skipped)`);
                return false;
            }
            return true;
        });

        if (validFiles.length > 0) {
            onFilesSelected(validFiles);
        } else {
            alert('Все выбранные файлы слишком большие (максимум 10MB).');
        }
    }, [maxFiles, onFilesSelected]);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        if (!disabled) {
            setIsDragOver(true);
        }
    }, [disabled]);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragOver(false);
        if (!disabled && e.dataTransfer.files.length > 0) {
            handleFiles(e.dataTransfer.files);
        }
    }, [disabled, handleFiles]);

    const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            handleFiles(e.target.files);
        }
    }, [handleFiles]);

    const handleClick = useCallback(() => {
        if (!disabled) {
            inputRef.current?.click();
        }
    }, [disabled]);

    return (
        <div
            onClick={handleClick}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            className={`
        aspect-video rounded-3xl flex flex-col items-center justify-center text-white shadow-xl 
        cursor-pointer transition-all duration-200
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'active:scale-95'}
        ${isDragOver
                    ? 'bg-gradient-to-br from-green-500 via-emerald-500 to-teal-500 scale-102'
                    : 'bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500'
                }
      `}
        >
            {isDragOver ? (
                <>
                    <Upload size={64} className="mb-4 animate-bounce" />
                    <span className="text-xl font-bold mb-2">Отпустите для загрузки</span>
                </>
            ) : (
                <>
                    <Camera size={64} className="mb-4" />
                    <span className="text-xl font-bold mb-2">
                        {isDesktop ? 'Загрузить фото' : 'Сфотографировать'}
                    </span>
                    <span className="text-sm text-white/80">
                        {isDesktop
                            ? 'Перетащите файлы или нажмите для выбора'
                            : `Можно выбрать до ${maxFiles} фото`
                        }
                    </span>
                </>
            )}

            <input
                ref={inputRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={handleInputChange}
                disabled={disabled}
            />
        </div>
    );
};
