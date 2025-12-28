import React, { useMemo, useState } from 'react';
import { Check, AlertCircle, X, ChevronLeft, ChevronRight, Flame, Drumstick, Droplets, Wheat, RefreshCcw, Camera } from 'lucide-react';
import type { RecognizedItem } from '../../api';
import type { PhotoQueueItem } from '../../model';
import { AI_ERROR_CODES, NON_RETRYABLE_ERROR_CODES } from '../../model';

interface BatchResultsModalProps {
    photoQueue: PhotoQueueItem[];
    onRetry: (id: string) => void;
    onRetryAll?: () => void;
    onRemove: (id: string) => void;
    onClose: () => void;
    /** Called when user wants to go back to camera (for cancelled batches) */
    onBackToCamera?: () => void;
}

export const BatchResultsModal: React.FC<BatchResultsModalProps> = ({
    photoQueue,
    onRetry,
    onRetryAll,
    onRemove,
    onClose,
    onBackToCamera,
}) => {
    const [selectedId, setSelectedId] = useState<string | null>(null);

    const totalCount = photoQueue.length;
    const successCount = photoQueue.filter((p) => p.status === 'success').length;
    // Retryable = all errors EXCEPT non-retryable codes (e.g., daily limit)
    const retryableCount = photoQueue.filter(
        (p) => p.status === 'error' && !NON_RETRYABLE_ERROR_CODES.has(p.errorCode || '')
    ).length;

    const selectedItem = useMemo(() => photoQueue.find((p) => p.id === selectedId), [photoQueue, selectedId]);

    if (selectedId && selectedItem) {
        return (
            <ResultDetailView
                photoItem={selectedItem}
                onClose={() => setSelectedId(null)}
                onRetry={
                    selectedItem.status === 'error'
                        ? () => {
                            setSelectedId(null);
                            onRetry(selectedItem.id);
                        }
                        : undefined
                }
                onRemove={() => {
                    setSelectedId(null);
                    onRemove(selectedItem.id);
                }}
            />
        );
    }

    return (
        <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-[60] animate-in fade-in duration-200">
            <div className="bg-white w-full max-w-lg sm:rounded-3xl rounded-t-3xl h-[98vh] sm:h-auto sm:max-h-[95vh] flex flex-col shadow-2xl animate-in slide-in-from-bottom duration-300">
                <div className="p-6 border-b border-gray-100 flex items-center justify-between shrink-0">
                    <div>
                        <h2 className="text-xl font-bold text-gray-900">Итоги загрузки</h2>
                        <p className="text-sm text-gray-500">
                            Распознано {successCount} из {totalCount} фото
                        </p>
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
                                            <div className="flex items-center gap-3 mt-2">
                                                <button
                                                    onClick={() => setSelectedId(item.id)}
                                                    className="text-sm text-blue-600 font-bold hover:bg-blue-50 px-2 py-1 rounded-lg transition-colors flex items-center gap-1"
                                                >
                                                    Детали <ChevronRight size={14} />
                                                </button>
                                                <button
                                                    onClick={() => onRemove(item.id)}
                                                    className="text-sm text-gray-400 font-medium hover:text-red-500 transition-colors flex items-center gap-1"
                                                >
                                                    <X size={14} />
                                                    Удалить
                                                </button>
                                            </div>
                                        </>
                                    ) : (
                                        <>
                                            <h3 className={`font-bold ${isCancelled ? 'text-gray-500' : 'text-red-600'}`}>
                                                {isCancelled ? 'Отменено' : 'Ошибка загрузки'}
                                            </h3>
                                            <p className="text-sm text-gray-500 mt-1 truncate">{item.error || 'Ошибка распознавания'}</p>
                                            <div className="flex gap-4 mt-2">
                                                <button
                                                    onClick={() => onRetry(item.id)}
                                                    className="text-sm text-blue-600 font-bold hover:bg-blue-50 px-2 py-1 rounded-lg transition-colors flex items-center gap-1"
                                                >
                                                    <RefreshCcw size={14} />
                                                    Повторить
                                                </button>
                                                <button
                                                    onClick={() => onRemove(item.id)}
                                                    className="text-sm text-red-500 font-medium hover:bg-red-50 px-2 py-1 rounded-lg transition-colors flex items-center gap-1"
                                                >
                                                    <X size={14} />
                                                    Удалить
                                                </button>
                                            </div>
                                        </>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>

                <div className="p-4 border-t border-gray-100 shrink-0 bg-white sm:rounded-b-3xl pb-[calc(1.5rem+env(safe-area-inset-bottom))] sm:pb-4 space-y-3">
                    {retryableCount >= 2 && onRetryAll && (
                        <button
                            onClick={onRetryAll}
                            className="w-full bg-blue-50 text-blue-600 py-4 rounded-2xl font-bold hover:bg-blue-100 transition-colors flex items-center justify-center gap-2"
                        >
                            <RefreshCcw size={18} />
                            Повторить все ({retryableCount})
                        </button>
                    )}

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
                            className="w-full bg-gray-100 text-gray-600 py-4 rounded-2xl font-bold hover:bg-gray-200 transition-colors"
                        >
                            Закрыть
                        </button>
                    )}
                </div>
            </div>
        </div>
    );
};

interface ResultDetailViewProps {
    photoItem: PhotoQueueItem;
    onClose: () => void;
    onRetry?: () => void;
    onRemove: () => void;
}

const ResultDetailView: React.FC<ResultDetailViewProps> = ({ photoItem, onClose, onRetry, onRemove }) => {
    const result = photoItem.result;

    const renderItemCard = (item: RecognizedItem, idx: number) => (
        <div key={idx} className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
            <div className="flex justify-between items-start mb-3">
                <div className="flex-1 min-w-0">
                    <h4 className="font-bold text-gray-900 text-lg leading-tight truncate">{item.name}</h4>
                    <p className="text-gray-500 text-sm mt-1">{item.grams} г</p>
                </div>
                <div className="flex items-center gap-1 bg-orange-50 px-3 py-1.5 rounded-xl ml-2 shrink-0">
                    <Flame size={16} className="text-orange-500" />
                    <span className="font-bold text-orange-700">{Math.round(item.calories)}</span>
                </div>
            </div>

            <div className="grid grid-cols-3 gap-2">
                <div className="bg-gray-50 rounded-xl p-2 flex flex-col items-center">
                    <div className="flex items-center gap-1 text-gray-500 text-xs mb-1">
                        <Drumstick size={12} />
                        <span>Белки</span>
                    </div>
                    <span className="font-bold text-gray-900">{Math.round(item.protein)}г</span>
                </div>
                <div className="bg-gray-50 rounded-xl p-2 flex flex-col items-center">
                    <div className="flex items-center gap-1 text-gray-500 text-xs mb-1">
                        <Droplets size={12} />
                        <span>Жиры</span>
                    </div>
                    <span className="font-bold text-gray-900">{Math.round(item.fat)}г</span>
                </div>
                <div className="bg-gray-50 rounded-xl p-2 flex flex-col items-center">
                    <div className="flex items-center gap-1 text-gray-500 text-xs mb-1">
                        <Wheat size={12} />
                        <span>Угл.</span>
                    </div>
                    <span className="font-bold text-gray-900">{Math.round(item.carbohydrates)}г</span>
                </div>
            </div>
        </div>
    );

    const isOk = photoItem.status === 'success' && !!result;
    const isCancelled = photoItem.status === 'error' && photoItem.errorCode === AI_ERROR_CODES.CANCELLED;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-[70] animate-in fade-in duration-200">
            <div className="bg-white w-full max-w-lg sm:rounded-3xl rounded-t-3xl h-[98vh] sm:h-auto sm:max-h-[95vh] flex flex-col shadow-2xl animate-in slide-in-from-bottom duration-300">
                <div className="p-6 border-b border-gray-100 flex items-center gap-3 shrink-0">
                    <button onClick={onClose} className="p-2 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors">
                        <ChevronLeft size={20} className="text-gray-600" />
                    </button>
                    <div className="flex-1">
                        <h2 className="text-xl font-bold text-gray-900">Детали блюда</h2>
                        <p className="text-sm text-gray-500 truncate">{photoItem.file.name}</p>
                    </div>
                    <button onClick={onRemove} className="p-2 text-gray-400 hover:text-red-500 transition-colors" title="Удалить">
                        <X size={20} />
                    </button>
                </div>

                <div className="overflow-y-auto flex-1">
                    <div className="w-full aspect-video bg-gray-200 relative">
                        {photoItem.previewUrl ? (
                            <img src={photoItem.previewUrl} alt="Detail" className="w-full h-full object-cover" />
                        ) : (
                            <div className="w-full h-full flex items-center justify-center text-sm text-gray-500">Нет превью</div>
                        )}
                    </div>

                    {isOk ? (
                        <div className="p-6 space-y-6">
                            <div className="grid grid-cols-4 gap-2 p-4 bg-gray-50 rounded-2xl border border-gray-100">
                                <div className="text-center border-r border-gray-200 last:border-0">
                                    <div className="text-xs text-gray-500 font-bold uppercase tracking-wider">Ккал</div>
                                    <div className="text-base font-bold text-orange-600">{Math.round(result!.total_calories)}</div>
                                </div>
                                <div className="text-center border-r border-gray-200 last:border-0">
                                    <div className="text-xs text-gray-500 font-bold uppercase tracking-wider">Белки</div>
                                    <div className="text-base font-bold text-gray-900">{Math.round(result!.total_protein)}</div>
                                </div>
                                <div className="text-center border-r border-gray-200 last:border-0">
                                    <div className="text-xs text-gray-500 font-bold uppercase tracking-wider">Жиры</div>
                                    <div className="text-base font-bold text-gray-900">{Math.round(result!.total_fat)}</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-xs text-gray-500 font-bold uppercase tracking-wider">Угл.</div>
                                    <div className="text-base font-bold text-gray-900">{Math.round(result!.total_carbohydrates)}</div>
                                </div>
                            </div>

                            <div className="space-y-4">
                                <h3 className="text-lg font-bold text-gray-900 flex items-center gap-2">
                                    Распознанные блюда
                                    <span className="bg-blue-100 text-blue-600 px-2 py-0.5 rounded-full text-sm">
                                        {result!.recognized_items.length}
                                    </span>
                                </h3>
                                <div className="space-y-3">{result!.recognized_items.map(renderItemCard)}</div>
                            </div>
                        </div>
                    ) : (
                        <div className="p-12 text-center flex flex-col items-center justify-center">
                            <div className={`w-16 h-16 rounded-full flex items-center justify-center mb-4 ${isCancelled ? 'bg-gray-100' : 'bg-red-50'}`}>
                                <AlertCircle size={32} className={isCancelled ? 'text-gray-400' : 'text-red-500'} />
                            </div>
                            <h3 className={`text-xl font-bold mb-2 ${isCancelled ? 'text-gray-500' : 'text-red-600'}`}>
                                {isCancelled ? 'Отменено' : 'Ошибка загрузки'}
                            </h3>
                            <p className="text-gray-500 max-w-xs mb-8">{photoItem.error || 'Попробуйте ещё раз'}</p>

                            {onRetry && (
                                <button
                                    onClick={onRetry}
                                    className="w-full max-w-xs bg-blue-600 text-white py-4 rounded-2xl font-bold hover:bg-blue-700 transition-colors flex items-center justify-center gap-2 shadow-lg active:scale-95 transition-all"
                                >
                                    <RefreshCcw size={20} />
                                    Повторить
                                </button>
                            )}
                        </div>
                    )}
                </div>

                <div className="h-[env(safe-area-inset-bottom)] bg-white shrink-0" />
            </div>
        </div>
    );
};
