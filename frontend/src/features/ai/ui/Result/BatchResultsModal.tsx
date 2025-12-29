import React, { useState } from 'react';
import { Check, AlertCircle, X, RefreshCcw, Camera, CheckCircle2 } from 'lucide-react';
import type { PhotoQueueItem } from '../../model';
import { AI_ERROR_CODES, NON_RETRYABLE_ERROR_CODES } from '../../model';

interface BatchResultsModalProps {
    photoQueue: PhotoQueueItem[];
    /** Retry multiple selected photos and start processing */
    onRetrySelected: (ids: string[]) => void;
    onClose: () => void;
    /** Called when user wants to go back to camera (for cancelled batches) */
    onBackToCamera?: () => void;
}

export const BatchResultsModal: React.FC<BatchResultsModalProps> = ({
    photoQueue,
    onRetrySelected,
    onClose,
    onBackToCamera,
}) => {
    // Multi-select state for retry
    const [selectedForRetry, setSelectedForRetry] = useState<Set<string>>(new Set());

    const totalCount = photoQueue.length;
    const successCount = photoQueue.filter((p) => p.status === 'success').length;
    // Retryable = all errors EXCEPT non-retryable codes (e.g., daily limit)
    const retryableCount = photoQueue.filter(
        (p) => p.status === 'error' && !NON_RETRYABLE_ERROR_CODES.has(p.errorCode || '')
    ).length;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-[60] animate-in fade-in duration-200">
            <div className="bg-white w-full max-w-lg sm:rounded-3xl rounded-t-3xl h-[98vh] sm:h-auto sm:max-h-[95vh] flex flex-col shadow-2xl animate-in slide-in-from-bottom duration-300">
                <div className="p-6 border-b border-gray-100 flex items-center justify-between shrink-0">
                    <div>
                        <h2 className="text-xl font-bold text-gray-900">Итоги загрузки</h2>
                        <p className="text-sm text-gray-500">
                            Распознано {successCount} из {totalCount} фото
                        </p>
                        {selectedForRetry.size > 0 && (
                            <p className="text-sm text-blue-600 font-medium mt-0.5">
                                Выбрано: {selectedForRetry.size} из {retryableCount}
                            </p>
                        )}
                    </div>
                    <button onClick={onClose} className="p-2 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors">
                        <X size={20} className="text-gray-600" />
                    </button>
                </div>

                <div className="overflow-y-auto p-4 space-y-4 flex-1">
                    {photoQueue.map((item) => {
                        const isOk = item.status === 'success' && !!item.result;
                        const isCancelled = item.status === 'error' && item.errorCode === AI_ERROR_CODES.CANCELLED;

                        return (
                            <div key={item.id} className="flex gap-4 p-3 bg-gray-50 rounded-2xl border border-gray-100 relative">
                                <div className="w-20 h-20 shrink-0 rounded-xl overflow-hidden bg-gray-200 relative aspect-square">
                                    {item.previewUrl ? (
                                        <img src={item.previewUrl} alt="Preview" className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-xs text-gray-500">Нет превью</div>
                                    )}
                                    <div
                                        className={`absolute top-1 right-1 w-6 h-6 rounded-full flex items-center justify-center ${isOk ? 'bg-green-500' : isCancelled ? 'bg-gray-400' : 'bg-red-500'
                                            }`}
                                    >
                                        {isOk ? <Check size={14} className="text-white" /> : <AlertCircle size={14} className="text-white" />}
                                    </div>
                                </div>

                                <div className="flex-1 min-w-0 flex flex-col justify-center">
                                    {isOk ? (
                                        <>
                                            <h3 className="font-bold text-gray-900 truncate pr-2">
                                                {item.result!.recognized_items.map((i) => i.name).join(', ') || 'Еда'}
                                            </h3>
                                            <div className="flex flex-wrap items-center gap-2 mt-1 text-sm text-gray-600">
                                                <span className="font-medium text-orange-600">
                                                    {Math.round(item.result!.total_calories)} ккал
                                                </span>
                                            </div>
                                        </>
                                    ) : (
                                        <>
                                            <h3 className={`font-bold ${isCancelled ? 'text-gray-500' : 'text-red-600'}`}>
                                                {isCancelled ? 'Отменено' : 'Ошибка загрузки'}
                                            </h3>
                                            <p className="text-sm text-gray-500 mt-1 truncate">{item.error || 'Ошибка распознавания'}</p>
                                            {/* Единственная кнопка: toggle выбора (только для retryable ошибок) */}
                                            {!NON_RETRYABLE_ERROR_CODES.has(item.errorCode || '') && (
                                                <div className="mt-2">
                                                    <button
                                                        onClick={() => {
                                                            setSelectedForRetry(prev => {
                                                                const next = new Set(prev);
                                                                if (next.has(item.id)) {
                                                                    next.delete(item.id);
                                                                } else {
                                                                    next.add(item.id);
                                                                }
                                                                return next;
                                                            });
                                                        }}
                                                        className={`text-sm font-bold px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 ${selectedForRetry.has(item.id)
                                                            ? 'bg-blue-600 text-white'
                                                            : 'text-blue-600 hover:bg-blue-50'
                                                            }`}
                                                    >
                                                        {selectedForRetry.has(item.id) ? (
                                                            <>
                                                                <X size={14} />
                                                                Снять
                                                            </>
                                                        ) : (
                                                            <>
                                                                <CheckCircle2 size={14} />
                                                                Выбрать
                                                            </>
                                                        )}
                                                    </button>
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>

                <div className="p-4 border-t border-gray-100 shrink-0 bg-white sm:rounded-b-3xl pb-[calc(1.5rem+env(safe-area-inset-bottom))] sm:pb-4 space-y-3">
                    {/* Режим B: показываем глобальную кнопку "Повторить выбранные" */}
                    {selectedForRetry.size > 0 && (
                        <button
                            onClick={() => {
                                onRetrySelected(Array.from(selectedForRetry));
                                setSelectedForRetry(new Set());
                            }}
                            className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-4 rounded-2xl font-bold hover:shadow-xl transition-all min-h-[48px] flex items-center justify-center gap-2 shadow-lg"
                        >
                            <RefreshCcw size={18} />
                            Повторить выбранные ({selectedForRetry.size})
                        </button>
                    )}

                    {/* Primary CTA: "Готово" если есть успешные фото, иначе "Вернуться в камеру" */}
                    {selectedForRetry.size === 0 && (
                        <>
                            {successCount > 0 ? (
                                <button
                                    onClick={onClose}
                                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-4 rounded-2xl font-bold hover:shadow-xl transition-all min-h-[48px] flex items-center justify-center shadow-lg"
                                >
                                    Готово
                                </button>
                            ) : onBackToCamera ? (
                                <button
                                    onClick={onBackToCamera}
                                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-4 rounded-2xl font-bold hover:shadow-xl transition-all min-h-[48px] flex items-center justify-center gap-2 shadow-lg"
                                >
                                    <Camera size={20} />
                                    Вернуться в камеру
                                </button>
                            ) : (
                                <button
                                    onClick={onClose}
                                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-4 rounded-2xl font-bold hover:shadow-xl transition-all min-h-[48px] flex items-center justify-center shadow-lg"
                                >
                                    Закрыть
                                </button>
                            )}
                        </>
                    )}

                    {/* Secondary CTA: "Вернуться в камеру" всегда доступна в режиме B */}
                    {selectedForRetry.size > 0 && onBackToCamera && (
                        <button
                            onClick={onBackToCamera}
                            className="w-full bg-gray-100 text-gray-600 py-4 rounded-2xl font-bold hover:bg-gray-200 transition-colors flex items-center justify-center gap-2"
                        >
                            <Camera size={18} />
                            Вернуться в камеру
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};
