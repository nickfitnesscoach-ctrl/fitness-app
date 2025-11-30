import React from 'react';
import { Check, AlertCircle, X, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

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
    meal_id?: number;
    photo_url?: string | null;
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
    const navigate = useNavigate();
    const successCount = results.filter(r => r.status === 'success').length;
    const totalCount = results.length;

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
                            <div className="w-20 h-20 shrink-0 rounded-xl overflow-hidden bg-gray-200 relative">
                                <img
                                    src={URL.createObjectURL(result.file)}
                                    alt="Preview"
                                    className="w-full h-full object-cover"
                                />
                                <div className={`absolute top-1 right-1 w-6 h-6 rounded-full flex items-center justify-center ${result.status === 'success' ? 'bg-green-500' : 'bg-red-500'
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
                                    <>
                                        <h3 className="font-bold text-gray-900 truncate">
                                            {result.data.recognized_items.map(i => i.name).join(', ') || 'Еда'}
                                        </h3>
                                        <div className="flex items-center gap-3 mt-1 text-sm text-gray-600">
                                            <span className="font-medium text-orange-600">
                                                {Math.round(result.data.total_calories)} ккал
                                            </span>
                                            <span className="text-xs bg-gray-200 px-1.5 py-0.5 rounded">
                                                Б {Math.round(result.data.total_protein)}
                                            </span>
                                            <span className="text-xs bg-gray-200 px-1.5 py-0.5 rounded">
                                                Ж {Math.round(result.data.total_fat)}
                                            </span>
                                            <span className="text-xs bg-gray-200 px-1.5 py-0.5 rounded">
                                                У {Math.round(result.data.total_carbohydrates)}
                                            </span>
                                        </div>
                                        {result.data?.meal_id && (
                                            <button
                                                onClick={() => navigate(`/meal/${result.data?.meal_id}`)}
                                                className="mt-2 text-sm text-blue-600 font-medium hover:underline text-left"
                                            >
                                                Подробнее
                                            </button>
                                        )}
                                    </>
                                ) : (
                                    <>
                                        <h3 className="font-bold text-red-600">Не распознано</h3>
                                        <p className="text-sm text-red-500 mt-1">
                                            {result.error || 'Попробуйте ещё раз'}
                                        </p>
                                    </>
                                )}
                            </div>
                        </div>
                    ))}
                </div>

                {/* Footer */}
                <div className="p-4 border-t border-gray-100 shrink-0 space-y-3 bg-white sm:rounded-b-3xl pb-8 sm:pb-4">
                    <button
                        onClick={onClose}
                        className="w-full bg-black text-white py-3.5 rounded-xl font-bold hover:bg-gray-800 transition-colors"
                    >
                        Готово
                    </button>

                    {onOpenDiary && (
                        <button
                            onClick={onOpenDiary}
                            className="w-full bg-gray-100 text-gray-900 py-3.5 rounded-xl font-bold hover:bg-gray-200 transition-colors flex items-center justify-center gap-2"
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
