import React from 'react';
import { X, Camera } from 'lucide-react';
import type { FileWithComment } from '../../model';

interface SelectedPhotosListProps {
    files: FileWithComment[];
    onChangeComment: (index: number, value: string) => void;
    onRemove: (index: number) => void;
    onAddFiles: (newFiles: File[]) => void;
    maxFiles?: number;
}

export const SelectedPhotosList: React.FC<SelectedPhotosListProps> = ({
    files,
    onChangeComment,
    onRemove,
    onAddFiles,
    maxFiles = 5
}) => {
    const handleFileInputChange = (event: React.ChangeEvent<HTMLInputElement>) => {
        if (event.target.files) {
            const newFiles = Array.from(event.target.files);
            if (files.length + newFiles.length > maxFiles) {
                alert(`Максимум ${maxFiles} фото`);
                return;
            }
            onAddFiles(newFiles);
        }
    };

    return (
        <div className="space-y-4">
            {/* Vertical list of photos with individual comment fields */}
            {files.map(({ file, comment, previewUrl }, index) => (
                <div key={index} className="bg-gray-50 rounded-2xl p-4 border border-gray-200">
                    <div className="flex gap-4">
                        {/* Photo Preview */}
                        <div className="relative shrink-0 w-24 h-24 rounded-xl overflow-hidden group">
                            <img
                                src={previewUrl || URL.createObjectURL(file)}
                                alt={`Preview ${index + 1}`}
                                className="w-full h-full object-cover"
                            />
                            <button
                                onClick={() => onRemove(index)}
                                className="absolute top-1 right-1 bg-red-500 text-white rounded-full p-1.5 opacity-0 group-hover:opacity-100 transition-opacity shadow-lg"
                            >
                                <X size={14} />
                            </button>
                            <div className="absolute bottom-1 left-1 bg-black/70 text-white text-xs px-2 py-0.5 rounded">
                                #{index + 1}
                            </div>
                        </div>

                        {/* Comment Input */}
                        <div className="flex-1 min-w-0">
                            <label className="block text-sm font-medium text-gray-700 mb-2">
                                Комментарий для фото #{index + 1}
                            </label>
                            <textarea
                                value={comment}
                                onChange={(e) => onChangeComment(index, e.target.value)}
                                placeholder={`Например: бургер 300 гр, картофель фри...`}
                                className="w-full bg-white border border-gray-300 rounded-xl p-3 text-sm text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all resize-none"
                                rows={3}
                            />
                        </div>
                    </div>
                </div>
            ))}

            {/* Add More Button */}
            {files.length < maxFiles && (
                <label className="block">
                    <div className="border-2 border-dashed border-gray-300 rounded-2xl p-4 flex items-center justify-center gap-3 text-gray-400 hover:border-blue-400 hover:text-blue-500 hover:bg-blue-50 transition-all cursor-pointer">
                        <Camera size={20} />
                        <span className="font-medium">Добавить ещё фото</span>
                    </div>
                    <input
                        type="file"
                        accept="image/*"
                        multiple
                        className="hidden"
                        onChange={handleFileInputChange}
                    />
                </label>
            )}
        </div>
    );
};
