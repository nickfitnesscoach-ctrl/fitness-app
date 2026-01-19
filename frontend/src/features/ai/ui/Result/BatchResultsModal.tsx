import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, Camera, Check, CheckCircle2, Copy, RefreshCcw, X } from 'lucide-react';

import type { PhotoQueueItem } from '../../model';
import { AI_ERROR_CODES, NON_RETRYABLE_ERROR_CODES, getErrorActionHint, getErrorTitle } from '../../model';
import { useBodyScrollLock } from '../../../../hooks/useBodyScrollLock';

interface BatchResultsModalProps {
    photoQueue: PhotoQueueItem[];
    /** Retry multiple selected photos and start processing */
    onRetrySelected: (ids: string[]) => void;
    onClose: () => void;
    /** Called when user wants to go back to camera (for cancelled batches) */
    onBackToCamera?: () => void;
    /** Controls scroll lock (required for proper iOS scroll lock lifecycle). */
    isOpen: boolean;
}

export const BatchResultsModal: React.FC<BatchResultsModalProps> = ({
    photoQueue,
    onRetrySelected,
    onClose,
    onBackToCamera,
    isOpen,
}) => {
    useBodyScrollLock(isOpen);

    // Multi-select state for retry
    const [selectedForRetry, setSelectedForRetry] = useState<Set<string>>(() => new Set());
    // Detailed error view state
    const [selectedError, setSelectedError] = useState<PhotoQueueItem | null>(null);

    const totalCount = photoQueue.length;
    const successCount = useMemo(
        () => photoQueue.filter((p) => p.status === 'success').length,
        [photoQueue],
    );

    // Retryable = cancelled OR error with retryable code
    const retryableCount = useMemo(() => {
        return photoQueue.filter((p) => {
            if (p.status === 'cancelled') return true;
            if (p.status !== 'error') return false;
            return !NON_RETRYABLE_ERROR_CODES.has(p.errorCode || '');
        }).length;
    }, [photoQueue]);

    const closeDetail = () => setSelectedError(null);

    const handleToggleRetry = (id: string) => {
        setSelectedForRetry((prev) => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const handleRetrySelected = () => {
        const ids = Array.from(selectedForRetry);
        if (ids.length === 0) return;
        onRetrySelected(ids);
        setSelectedForRetry(new Set());
    };

    const primaryMode = selectedForRetry.size === 0;

    return (
        <div
            className="fixed inset-0 bg-black/50 flex items-end sm:items-center justify-center z-[60] animate-in fade-in duration-200"
            role="dialog"
            aria-modal="true"
            aria-label="Итоги загрузки"
        >
            <div className="bg-white w-full max-w-lg sm:rounded-3xl rounded-t-3xl h-[98vh] sm:h-auto sm:max-h-[95vh] flex flex-col shadow-2xl animate-in slide-in-from-bottom duration-300">
                {/* Header */}
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

                    <button
                        onClick={onClose}
                        className="p-2 bg-gray-100 rounded-full hover:bg-gray-200 transition-colors"
                        aria-label="Закрыть"
                        type="button"
                    >
                        <X size={20} className="text-gray-600" />
                    </button>
                </div>

                {/* List */}
                <div className="overflow-y-auto p-4 space-y-4 flex-1">
                    {photoQueue.map((item) => {
                        const isOk = item.status === 'success' && !!item.result;

                        // Cancelled can appear as either explicit status OR errorCode=CANCELLED (legacy)
                        const isCancelled =
                            item.status === 'cancelled' ||
                            (item.status === 'error' && item.errorCode === AI_ERROR_CODES.CANCELLED);

                        const isErrorState = !isOk;
                        const canShowMoreInfo = item.status === 'error' && !isCancelled;

                        const canSelectForRetry =
                            item.status === 'cancelled' ||
                            (item.status === 'error' && !NON_RETRYABLE_ERROR_CODES.has(item.errorCode || ''));

                        const isSelected = item.id ? selectedForRetry.has(item.id) : false;

                        return (
                            <div
                                key={item.id}
                                className="flex gap-4 p-3 bg-gray-50 rounded-2xl border border-gray-100 relative"
                            >
                                {/* Preview */}
                                <div className="w-20 h-20 shrink-0 rounded-xl overflow-hidden bg-gray-200 relative aspect-square">
                                    {item.previewUrl ? (
                                        <img src={item.previewUrl} alt="Preview" className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-xs text-gray-500">
                                            Нет превью
                                        </div>
                                    )}

                                    <div
                                        className={[
                                            'absolute top-1 right-1 w-6 h-6 rounded-full flex items-center justify-center',
                                            isOk ? 'bg-green-500' : isCancelled ? 'bg-gray-400' : 'bg-red-500',
                                        ].join(' ')}
                                        aria-hidden="true"
                                    >
                                        {isOk ? (
                                            <Check size={14} className="text-white" />
                                        ) : (
                                            <AlertCircle size={14} className="text-white" />
                                        )}
                                    </div>
                                </div>

                                {/* Content */}
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
                                                {isCancelled ? 'Отменено' : getErrorTitle(item.errorCode)}
                                            </h3>

                                            <p
                                                className={[
                                                    'text-sm text-gray-500 mt-1',
                                                    isCancelled ? 'truncate' : 'line-clamp-2',
                                                ].join(' ')}
                                            >
                                                {isCancelled ? 'Анализ был остановлен' : item.error || 'Ошибка распознавания'}
                                            </p>

                                            {canShowMoreInfo && (
                                                <button
                                                    onClick={() => setSelectedError(item)}
                                                    className="text-xs font-semibold text-blue-600 mt-1 hover:underline text-left w-fit"
                                                    type="button"
                                                >
                                                    Подробнее
                                                </button>
                                            )}

                                            {isErrorState && canSelectForRetry && (
                                                <div className="mt-2">
                                                    <button
                                                        onClick={() => item.id && handleToggleRetry(item.id)}
                                                        className={[
                                                            'text-sm font-bold px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5',
                                                            isSelected
                                                                ? 'bg-blue-600 text-white'
                                                                : 'text-blue-600 hover:bg-blue-50',
                                                        ].join(' ')}
                                                        type="button"
                                                    >
                                                        {isSelected ? (
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

                {/* Footer */}
                <div className="p-4 border-t border-gray-100 shrink-0 bg-white sm:rounded-b-3xl pb-[calc(1.5rem+env(safe-area-inset-bottom))] sm:pb-4 space-y-3">
                    {/* Mode B: global "Retry selected" */}
                    {selectedForRetry.size > 0 && (
                        <button
                            onClick={handleRetrySelected}
                            className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-4 rounded-2xl font-bold hover:shadow-xl transition-all min-h-[48px] flex items-center justify-center gap-2 shadow-lg"
                            type="button"
                        >
                            <RefreshCcw size={18} />
                            Повторить выбранные ({selectedForRetry.size})
                        </button>
                    )}

                    {/* Primary CTA */}
                    {primaryMode && (
                        <>
                            {successCount > 0 ? (
                                <button
                                    onClick={onClose}
                                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-4 rounded-2xl font-bold hover:shadow-xl transition-all min-h-[48px] flex items-center justify-center shadow-lg"
                                    type="button"
                                >
                                    Готово
                                </button>
                            ) : onBackToCamera ? (
                                <button
                                    onClick={onBackToCamera}
                                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-4 rounded-2xl font-bold hover:shadow-xl transition-all min-h-[48px] flex items-center justify-center gap-2 shadow-lg"
                                    type="button"
                                >
                                    <Camera size={20} />
                                    Вернуться в камеру
                                </button>
                            ) : (
                                <button
                                    onClick={onClose}
                                    className="w-full bg-gradient-to-r from-blue-600 to-purple-600 text-white py-4 rounded-2xl font-bold hover:shadow-xl transition-all min-h-[48px] flex items-center justify-center shadow-lg"
                                    type="button"
                                >
                                    Закрыть
                                </button>
                            )}
                        </>
                    )}

                    {/* Secondary CTA: always available in Mode B */}
                    {selectedForRetry.size > 0 && onBackToCamera && (
                        <button
                            onClick={onBackToCamera}
                            className="w-full bg-gray-100 text-gray-600 py-4 rounded-2xl font-bold hover:bg-gray-200 transition-colors flex items-center justify-center gap-2"
                            type="button"
                        >
                            <Camera size={18} />
                            Вернуться в камеру
                        </button>
                    )}
                </div>
            </div>

            {/* Error Detail Modal (Secondary Bottom Sheet) */}
            {selectedError && <ErrorDetailModal item={selectedError} onClose={closeDetail} />}
        </div>
    );
};

interface ErrorDetailModalProps {
    item: PhotoQueueItem;
    onClose: () => void;
}

const ErrorDetailModal: React.FC<ErrorDetailModalProps> = ({ item, onClose }) => {
    const [copied, setCopied] = useState(false);
    const timeoutRef = useRef<number | null>(null);

    useEffect(() => {
        return () => {
            if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
        };
    }, []);

    const shortId = item.id ? `${item.id.slice(0, 8)}...` : 'n/a';

    const hints = useMemo(() => {
        const specificHint = getErrorActionHint(item.errorCode);
        return [
            specificHint || 'Проверьте стабильность интернет-соединения',
            'Попробуйте сделать новое фото еды',
            'Повторите попытку немного позже',
        ];
    }, [item.errorCode]);

    const buildSupportText = () => {
        return `EatFit24 — ошибка обработки фото
Сообщение: ${item.error || 'Ошибка распознавания'}
Код ошибки: ${item.errorCode || 'UNKNOWN'}
ID: ${item.id || 'n/a'}
Дата: ${new Date().toISOString()}`;
    };

    const copyTextFallback = (text: string): boolean => {
        const ta = document.createElement('textarea');
        ta.value = text;
        ta.setAttribute('readonly', '');
        ta.style.position = 'fixed';
        ta.style.left = '-9999px';
        ta.style.top = '0';
        document.body.appendChild(ta);

        try {
            ta.focus();
            ta.select();
            ta.setSelectionRange(0, ta.value.length); // iOS WebView helper
            return document.execCommand('copy');
        } finally {
            document.body.removeChild(ta);
        }
    };

    const handleCopy = async () => {
        const text = buildSupportText();

        try {
            const ok =
                (navigator.clipboard?.writeText
                    ? await navigator.clipboard.writeText(text).then(() => true).catch(() => false)
                    : false) || copyTextFallback(text);

            if (!ok) throw new Error('Copy failed');

            setCopied(true);
            if (timeoutRef.current) window.clearTimeout(timeoutRef.current);
            timeoutRef.current = window.setTimeout(() => setCopied(false), 2000);
        } catch (err) {
            // eslint-disable-next-line no-console
            console.error('Failed to copy text:', err);
            alert('Не удалось скопировать. Пожалуйста, сделайте скриншот ошибки.');
        }
    };

    return (
        <div
            className="fixed inset-0 bg-black/40 flex items-end sm:items-center justify-center z-[70] animate-in fade-in duration-200"
            onClick={onClose}
            role="dialog"
            aria-modal="true"
            aria-label="Что пошло не так"
        >
            <div
                className="bg-white w-full max-w-md sm:rounded-3xl rounded-t-3xl shadow-2xl animate-in slide-in-from-bottom duration-300 overflow-hidden"
                onClick={(e) => e.stopPropagation()}
            >
                <div className="p-5 border-b border-gray-100 flex items-center justify-between">
                    <h3 className="text-lg font-bold text-gray-900">Что пошло не так</h3>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-gray-100 rounded-full transition-colors"
                        aria-label="Закрыть"
                        type="button"
                    >
                        <X size={20} className="text-gray-500" />
                    </button>
                </div>

                <div className="p-6 space-y-6 max-h-[70vh] overflow-y-auto">
                    <div>
                        <h4 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-2">Ошибка</h4>
                        <p className="text-gray-900 font-medium leading-relaxed">
                            {item.error ||
                                'Непредвиденная ошибка при обработке фотографии. Пожалуйста, попробуйте еще раз.'}
                        </p>
                    </div>

                    <div>
                        <h4 className="text-sm font-bold text-gray-400 uppercase tracking-wider mb-2">
                            Что можно сделать
                        </h4>
                        <ul className="space-y-2">
                            {hints.map((h, i) => (
                                <li key={i} className="flex gap-2 text-sm text-gray-600">
                                    <span className="text-blue-500 font-bold">•</span>
                                    {h}
                                </li>
                            ))}
                        </ul>
                    </div>

                    <div className="bg-gray-50 rounded-2xl p-4 space-y-2">
                        <div className="flex justify-between text-[11px] text-gray-400 font-mono uppercase">
                            <span>Код: {item.errorCode || 'UNKNOWN'}</span>
                            <span>ID: {shortId}</span>
                        </div>

                        <button
                            onClick={handleCopy}
                            className={[
                                'w-full flex items-center justify-center gap-2 py-3 rounded-xl text-sm font-bold transition-all',
                                copied
                                    ? 'bg-green-100 text-green-700'
                                    : 'bg-white border border-gray-200 text-gray-700 hover:border-blue-400 hover:text-blue-600 shadow-sm',
                            ].join(' ')}
                            type="button"
                        >
                            {copied ? <Check size={16} /> : <Copy size={16} />}
                            {copied ? 'Скопировано!' : 'Скопировать для поддержки'}
                        </button>
                    </div>
                </div>

                <div className="p-4 bg-gray-50 border-t border-gray-100">
                    <button
                        onClick={onClose}
                        className="w-full py-4 bg-white border border-gray-200 text-gray-900 rounded-2xl font-bold active:scale-[0.98] transition-all shadow-sm"
                        type="button"
                    >
                        Понятно
                    </button>
                </div>
            </div>
        </div>
    );
};
