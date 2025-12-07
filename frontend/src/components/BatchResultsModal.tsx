import React, { useState } from 'react';
import { Check, AlertCircle, X, ChevronRight, ChevronLeft, Flame, Drumstick, Droplets, Wheat } from 'lucide-react';

export interface RecognizedItem {
    name: string;
    grams: number;
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

export interface AnalysisResult {
    recognized_items: RecognizedItem[];
    total_calories: number;
    total_protein: number;
    total_fat: number;
    total_carbohydrates: number;
    meal_id?: number | string;
    photo_url?: string | null;
    _neutralMessage?: string; // UI hotfix: нейтральное сообщение вместо "Еда не найдена"
}

export interface BatchResult {
    file: File;
    status: 'success' | 'error';
    data?: AnalysisResult;
    error?: string;
}

interface BatchResultsModalProps {
    results: BatchResult[];
    onClose: () => void;
    onOpenDiary?: () => void;
    mealId?: number | null;
}

export const BatchResultsModal: React.FC<BatchResultsModalProps> = ({ results, onClose, onOpenDiary }) => {
    const successCount = results.filter(r => r.status === 'success').length;
    const totalCount = results.length;

    // Detail view state
    const [selectedResultIndex, setSelectedResultIndex] = useState<number | null>(null);

    const handleBackToList = () => {
        setSelectedResultIndex(null);
    };

    const handleViewDetails = (index: number) => {
        setSelectedResultIndex(index);
    };

    // If viewing details of a specific result
    if (selectedResultIndex !== null) {
        const result = results[selectedResultIndex];

        return (
            <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50 animate-in fade-in duration-200">
                <div className="bg-white w-full max-w-lg sm:rounded-3xl rounded-t-3xl max-h-[90vh] flex flex-col shadow-2xl animate-in slide-in-from-bottom duration-300">

                    {/* Detail View Header */}
                    <div className="p-6 border-b border-gray-100 flex items-center gap-3 shrink-0">
                        <button
                            onClick={handleBackToList}
                            className="p-2 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
                        >
                            <ChevronLeft size={20} className="text-gray-600" />
                        </button>
                        <div className="flex-1">
                            <h2 className="text-xl font-bold text-gray-900">Детали блюда</h2>
                            <p className="text-sm text-gray-500">
                                Фото {selectedResultIndex + 1} из {totalCount}
                            </p>
                        </div>
                    </div>

                    {/* Detail View Content */}
                    <div className="overflow-y-auto flex-1">
                        {/* Large Photo */}
                        {/* Large Photo - F-009: 1:1 Aspect Ratio Fix */}
                        <div className="w-full aspect-square bg-gray-200 relative">
                            <img
                                src={URL.createObjectURL(result.file)}
                                alt="Detail"
                                className="w-full h-full object-cover"
                            />
                        </div>

                        {result.status === 'success' && result.data ? (
                            <div className="p-6 space-y-4">
                                {/* Neutral message for empty items but successful processing */}
                                {result.data._neutralMessage ? (
                                    <div className="bg-blue-50 border border-blue-200 rounded-2xl p-6 text-center">
                                        <Check className="text-blue-500 mx-auto mb-3" size={48} />
                                        <h3 className="text-xl font-bold text-blue-600 mb-2">Анализ завершён</h3>
                                        <p className="text-blue-500">
                                            {result.data._neutralMessage}
                                        </p>
                                    </div>
                                ) : (
                                    <>
                                        {/* Summary */}
                                        <div className="bg-gradient-to-br from-orange-500 to-red-500 rounded-2xl p-4 text-white">
                                            <div className="flex items-center gap-2 mb-2">
                                                <Flame size={20} />
                                                <span className="font-bold text-lg">Итого</span>
                                            </div>
                                            <div className="text-3xl font-bold mb-3">
                                                {Math.round(result.data.total_calories)} ккал
                                            </div>
                                            <div className="grid grid-cols-3 gap-2 text-sm">
                                                <div className="bg-white/20 rounded-lg p-2 text-center">
                                                    <div className="font-medium">Б</div>
                                                    <div className="text-lg font-bold">{Math.round(result.data.total_protein)}г</div>
                                                </div>
                                                <div className="bg-white/20 rounded-lg p-2 text-center">
                                                    <div className="font-medium">Ж</div>
                                                    <div className="text-lg font-bold">{Math.round(result.data.total_fat)}г</div>
                                                </div>
                                                <div className="bg-white/20 rounded-lg p-2 text-center">
                                                    <div className="font-medium">У</div>
                                                    <div className="text-lg font-bold">{Math.round(result.data.total_carbohydrates)}г</div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Recognized Items */}
                                        <div>
                                            <h3 className="text-lg font-bold text-gray-900 mb-3">
                                                Распознанные блюда ({result.data.recognized_items.length})
                                            </h3>
                                            <div className="space-y-3">
                                                {result.data.recognized_items.map((item, idx) => (
                                                    <div key={idx} className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
                                                        <div className="flex justify-between items-start mb-3">
                                                            <div>
                                                                <h4 className="font-bold text-gray-900 text-lg leading-tight">
                                                                    {item.name}
                                                                </h4>
                                                                <p className="text-gray-500 text-sm mt-1">
                                                                    {item.grams} г
                                                                </p>
                                                            </div>
                                                            <div className="flex items-center gap-1 bg-orange-50 px-3 py-1.5 rounded-xl">
                                                                <Flame size={16} className="text-orange-500" />
                                                                <span className="font-bold text-orange-700">
                                                                    {Math.round(item.calories)}
                                                                </span>
                                                            </div>
                                                        </div>

                                                        {/* Macros */}
                                                        <div className="grid grid-cols-3 gap-2">
                                                            <div className="bg-gray-50 rounded-xl p-2 flex flex-col items-center">
                                                                <div className="flex items-center gap-1 text-gray-500 text-xs mb-1">
                                                                    <Drumstick size={12} />
                                                                    <span>Белки</span>
                                                                </div>
                                                                <span className="font-bold text-gray-900">{item.protein}г</span>
                                                            </div>
                                                            <div className="bg-gray-50 rounded-xl p-2 flex flex-col items-center">
                                                                <div className="flex items-center gap-1 text-gray-500 text-xs mb-1">
                                                                    <Droplets size={12} />
                                                                    <span>Жиры</span>
                                                                </div>
                                                                <span className="font-bold text-gray-900">{item.fat}г</span>
                                                            </div>
                                                            <div className="bg-gray-50 rounded-xl p-2 flex flex-col items-center">
                                                                <div className="flex items-center gap-1 text-gray-500 text-xs mb-1">
                                                                    <Wheat size={12} />
                                                                    <span>Угл.</span>
                                                                </div>
                                                                <span className="font-bold text-gray-900">{item.carbohydrates}г</span>
                                                            </div>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    </>
                                )}
                            </div>
                        ) : (
                            <div className="p-6">
                                <div className="bg-gray-50 border border-gray-200 rounded-2xl p-6 text-center">
                                    <AlertCircle className="text-gray-500 mx-auto mb-3" size={48} />
                                    <h3 className="text-xl font-bold text-gray-600 mb-2">Ошибка загрузки</h3>
                                    <p className="text-gray-500">
                                        {result.error || 'Попробуйте ещё раз'}
                                    </p>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Footer */}
                    <div className="p-4 border-t border-gray-100 shrink-0 bg-white sm:rounded-b-3xl pb-8 sm:pb-4">
                        <button
                            onClick={handleBackToList}
                            className="w-full bg-black text-white py-3.5 rounded-xl font-bold hover:bg-gray-800 transition-colors"
                        >
                            Назад к списку
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    // Default: List View
    return (
        <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-50 animate-in fade-in duration-200">
            <div className="bg-white w-full max-w-lg sm:rounded-3xl rounded-t-3xl max-h-[90vh] flex flex-col shadow-2xl animate-in slide-in-from-bottom duration-300">

                {/* Header */}
                <div className="p-6 border-b border-gray-100 flex items-center justify-between shrink-0">
                    <div>
                        <h2 className="text-xl font-bold text-gray-900">Итоги загрузки</h2>
                        <p className="text-sm text-gray-500">
                            Распознано {successCount} из {totalCount} фото
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="p-2 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
                    >
                        <X size={20} className="text-gray-600" />
                    </button>
                </div>

                {/* List */}
                <div className="overflow-y-auto p-4 space-y-4">
                    {results.map((result, index) => (
                        <div key={index} className="flex gap-4 p-3 bg-gray-50 rounded-2xl border border-gray-100 relative group">
                            {/* Thumbnail */}
                            {/* Thumbnail - F-009: 1:1 Ratio */}
                            <div className="w-20 h-20 shrink-0 rounded-xl overflow-hidden bg-gray-200 relative aspect-square">
                                <img
                                    src={URL.createObjectURL(result.file)}
                                    alt="Preview"
                                    className="w-full h-full object-cover"
                                />
                                <div className={`absolute top-1 right-1 w-6 h-6 rounded-full flex items-center justify-center ${result.status === 'success'
                                        ? (result.data?._neutralMessage ? 'bg-blue-500' : 'bg-green-500')
                                        : 'bg-gray-500'
                                    }`}>
                                    {result.status === 'success' ? (
                                        <Check size={14} className="text-white" />
                                    ) : (
                                        <AlertCircle size={14} className="text-white" />
                                    )}
                                </div>
                            </div>

                            {/* Content */}
                            <div className="flex-1 min-w-0 flex flex-col justify-center">
                                {result.status === 'success' && result.data ? (
                                    result.data._neutralMessage ? (
                                        // Neutral message for empty items but successful processing
                                        <>
                                            <h3 className="font-bold text-blue-600">Анализ завершён</h3>
                                            <p className="text-sm text-blue-500 mt-1">
                                                {result.data._neutralMessage}
                                            </p>
                                            <button
                                                onClick={() => handleViewDetails(index)}
                                                className="mt-2 text-sm text-blue-600 font-medium hover:underline text-left"
                                            >
                                                Подробнее
                                            </button>
                                        </>
                                    ) : (
                                        // Normal success with recognized items
                                        <>
                                            <h3 className="font-bold text-gray-900 truncate pr-2">
                                                {result.data.recognized_items.map(i => i.name).join(', ') || 'Еда'}
                                            </h3>
                                            <div className="flex flex-wrap items-center gap-2 mt-1 text-sm text-gray-600">
                                                <span className="font-medium text-orange-600">
                                                    {Math.round(result.data.total_calories)} ккал
                                                </span>
                                                <span className="text-xs bg-gray-200 px-1.5 py-0.5 rounded">
                                                    Б {Math.round(result.data.total_protein)}
                                                </span>
                                                <span className="text-xs bg-gray-200 px-1.5 py-0.5 rounded">
                                                    Ж {Math.round(result.data.total_fat)}
                                                </span>
                                                <span className="text-xs bg-gray-200 px-1.5 py-0.5 rounded whitespace-nowrap">
                                                    У {Math.round(result.data.total_carbohydrates)}
                                                </span>
                                            </div>
                                            <button
                                                onClick={() => handleViewDetails(index)}
                                                className="mt-2 text-sm text-blue-600 font-medium hover:underline text-left"
                                            >
                                                Подробнее
                                            </button>
                                        </>
                                    )
                                ) : (
                                    // Real error (network/server failure)
                                    <>
                                        <h3 className="font-bold text-gray-600">Ошибка загрузки</h3>
                                        <p className="text-sm text-gray-500 mt-1">
                                            {result.error || 'Попробуйте ещё раз'}
                                        </p>
                                    </>
                                )}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Footer */}
                {/* Footer - F-003, F-010: Min height & Safe Area */}
                <div className="p-4 border-t border-gray-100 shrink-0 space-y-3 bg-white sm:rounded-b-3xl pb-[calc(1.5rem+env(safe-area-inset-bottom))] sm:pb-4">
                    <button
                        onClick={onClose}
                        className="w-full bg-black text-white py-3.5 rounded-xl font-bold hover:bg-gray-800 transition-colors min-h-[48px] flex items-center justify-center"
                    >
                        Готово
                    </button>

                    {onOpenDiary && (
                        <button
                            onClick={onOpenDiary}
                            className="w-full bg-gray-100 text-gray-900 py-3.5 rounded-xl font-bold hover:bg-gray-200 transition-colors flex items-center justify-center gap-2 min-h-[48px]"
                        >
                            Открыть дневник
                            <ChevronRight size={18} />
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};
