import React, { useState, useEffect, useRef } from 'react';
import { AlertCircle, Check, X, Send } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useBilling } from '../contexts/BillingContext';
import { useAuth } from '../contexts/AuthContext';
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';

import {
    useFoodBatchAnalysis,
    BatchResultsModal,
    SelectedPhotosList,
    BatchProcessingScreen,
    LimitReachedModal,
    UploadDropzone,
    isHeicFile,
    convertHeicToJpeg,
    MEAL_TYPE_OPTIONS,
    AI_LIMITS,
    AI_ERROR_CODES,
} from '../features/ai';
import type { FileWithComment } from '../features/ai';

const FoodLogPage: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const billing = useBilling();
    const { isBrowserDebug } = useAuth();
    const { isReady, isTelegramWebApp: webAppDetected, isBrowserDebug: webAppBrowserDebug, isDesktop } = useTelegramWebApp();

    const getInitialDate = () => {
        const dateFromState = (location.state as any)?.selectedDate;
        return dateFromState ? new Date(dateFromState) : new Date();
    };

    const [selectedDate, setSelectedDate] = useState<Date>(getInitialDate());
    const [mealType, setMealType] = useState<string>('breakfast');
    const [selectedFiles, setSelectedFiles] = useState<FileWithComment[]>([]);
    const [showBatchResults, setShowBatchResults] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [showLimitModal, setShowLimitModal] = useState(false);

    const selectedFilesRef = useRef<FileWithComment[]>([]);
    selectedFilesRef.current = selectedFiles;

    const {
        isProcessing,
        photoQueue,
        startBatch,
        retryPhoto,
        removePhoto,
        cancelBatch,
        cleanup,
    } = useFoodBatchAnalysis({
        onDailyLimitReached: () => setShowLimitModal(true),
        getDateString: () => selectedDate.toISOString().split('T')[0],
        getMealType: () => mealType,
    });

    // unmount cleanup
    useEffect(() => {
        return () => {
            cleanup();
            // revoke parent-owned urls (если остались до startBatch)
            selectedFilesRef.current.forEach((f) => {
                if (f.previewUrl) URL.revokeObjectURL(f.previewUrl);
            });
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // auto-open results when finished (ALWAYS, even with errors)
    useEffect(() => {
        const allDone =
            photoQueue.length > 0 &&
            photoQueue.every((p) => p.status === 'success' || p.status === 'error');

        if (allDone && !isProcessing) {
            setShowBatchResults(true);
            if (selectedFilesRef.current.length > 0) setSelectedFiles([]);
            billing.refresh();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [photoQueue, isProcessing]);

    const buildFileWithComment = async (file: File): Promise<FileWithComment> => {
        if (isHeicFile(file)) {
            try {
                const converted = await convertHeicToJpeg(file);
                return { file: converted, comment: '', previewUrl: URL.createObjectURL(converted) };
            } catch {
                // even in fallback, create preview for original
                return { file, comment: '', previewUrl: URL.createObjectURL(file) };
            }
        }
        return { file, comment: '', previewUrl: URL.createObjectURL(file) };
    };

    const handleFilesSelected = async (files: File[]) => {
        const filesWithComments = await Promise.all(files.map(buildFileWithComment));
        setSelectedFiles(filesWithComments);
        setError(null);
    };

    const handleAddFiles = async (newFiles: File[]) => {
        const more = await Promise.all(newFiles.map(buildFileWithComment));
        setSelectedFiles((prev) => [...prev, ...more]);
    };

    const handleRemoveFile = (index: number) => {
        setSelectedFiles((prev) => {
            const next = [...prev];
            const item = next[index];
            if (item?.previewUrl) URL.revokeObjectURL(item.previewUrl);
            next.splice(index, 1);
            return next;
        });
    };

    const handleCommentChange = (index: number, comment: string) => {
        setSelectedFiles((prev) => {
            const next = [...prev];
            next[index] = { ...next[index], comment };
            return next;
        });
    };

    const clearSelectedFiles = () => {
        selectedFiles.forEach((f) => {
            if (f.previewUrl) URL.revokeObjectURL(f.previewUrl);
        });
        setSelectedFiles([]);
    };

    const handleAnalyze = () => {
        if (selectedFiles.length === 0) return;

        // startBatch: hook takes ownership of previewUrl
        startBatch(selectedFiles);

        // parent drops references WITHOUT revoke
        setSelectedFiles([]);
    };

    const handleCloseResults = () => {
        setShowBatchResults(false);
        cleanup(); // revoke hook-owned URLs
        const dateStr = selectedDate.toISOString().split('T')[0];
        navigate(`/?date=${dateStr}`);
    };

    if (!isReady) {
        return (
            <div className="min-h-screen min-h-dvh flex items-center justify-center">
                <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    if (!webAppDetected && !isBrowserDebug && !webAppBrowserDebug) {
        return (
            <div className="min-h-screen min-h-dvh flex items-center justify-center p-4">
                <div className="bg-orange-50 border-2 border-orange-200 rounded-2xl p-6 text-center max-w-md">
                    <h2 className="text-xl font-bold text-orange-900 mb-2">Откройте через Telegram</h2>
                    <p className="text-orange-700">
                        Это приложение работает только внутри Telegram. Откройте бота и нажмите “Открыть приложение”.
                    </p>
                </div>
            </div>
        );
    }

    const showProcessing = isProcessing || (photoQueue.length > 0 && !showBatchResults);

    return (
        <div className="min-h-screen min-h-dvh bg-gradient-to-br from-blue-50 via-white to-purple-50 p-4 pt-6 pb-[calc(6rem+env(safe-area-inset-bottom))]">
            <div className="max-w-lg mx-auto">
                <div className="bg-white rounded-3xl shadow-sm p-4 mb-6">
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <div>
                            <h3 className="text-sm font-semibold text-gray-700 mb-2">Дата</h3>
                            <input
                                type="date"
                                value={selectedDate.toISOString().split('T')[0]}
                                onChange={(e) => setSelectedDate(new Date(e.target.value))}
                                className="w-full p-3 rounded-xl border border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all bg-white"
                            />
                        </div>
                        <div>
                            <h3 className="text-sm font-semibold text-gray-700 mb-2">Приём пищи</h3>
                            <div className="relative">
                                <select
                                    value={mealType}
                                    onChange={(e) => setMealType(e.target.value)}
                                    className="w-full p-3 rounded-xl border border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all bg-white appearance-none"
                                >
                                    {MEAL_TYPE_OPTIONS.map((option) => (
                                        <option key={option.value} value={option.value}>
                                            {option.label}
                                        </option>
                                    ))}
                                </select>
                                <div className="absolute inset-y-0 right-0 flex items-center px-2 pointer-events-none">
                                    <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19 9l-7 7-7-7" />
                                    </svg>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {showProcessing ? (
                    <BatchProcessingScreen
                        photoQueue={photoQueue}
                        onRetry={retryPhoto}
                        onRetryAll={() => {
                            photoQueue.forEach((p) => {
                                if (p.status === 'error' && p.errorCode !== AI_ERROR_CODES.CANCELLED) retryPhoto(p.id);
                            });
                        }}
                        onShowResults={() => setShowBatchResults(true)}
                        onCancel={cancelBatch}
                    />
                ) : selectedFiles.length > 0 ? (
                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
                        <div className="bg-white rounded-3xl p-6 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-lg font-bold text-gray-900">Выбранные фото ({selectedFiles.length})</h2>
                                <button onClick={clearSelectedFiles} className="text-gray-400 hover:text-gray-600">
                                    <X size={20} />
                                </button>
                            </div>

                            <SelectedPhotosList
                                files={selectedFiles}
                                onChangeComment={handleCommentChange}
                                onRemove={handleRemoveFile}
                                onAddFiles={handleAddFiles}
                                maxFiles={AI_LIMITS.MAX_PHOTOS_PER_UPLOAD}
                            />

                            <div className="mt-4 bg-blue-50 border border-blue-200 rounded-xl p-3">
                                <p className="text-blue-800 text-sm">
                                    💡 <strong>Совет:</strong> Комментарий к каждому фото повышает точность распознавания
                                </p>
                            </div>

                            <div className="mt-6 grid grid-cols-2 gap-3">
                                <button
                                    onClick={clearSelectedFiles}
                                    className="py-3 px-4 rounded-xl font-bold text-gray-600 bg-gray-100 hover:bg-gray-200 transition-colors"
                                >
                                    Отмена
                                </button>
                                <button
                                    onClick={handleAnalyze}
                                    className="py-3 px-4 rounded-xl font-bold text-white bg-blue-600 hover:bg-blue-700 transition-colors flex items-center justify-center gap-2"
                                >
                                    <Send size={18} />
                                    Отправить
                                </button>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-6">
                        {isDesktop && (
                            <div className="bg-yellow-50 border border-yellow-200 rounded-2xl p-4">
                                <div className="flex items-start gap-3">
                                    <AlertCircle className="text-yellow-600 shrink-0 mt-0.5" size={20} />
                                    <div>
                                        <p className="text-yellow-800 font-medium text-sm">Вы используете десктоп-версию</p>
                                        <p className="text-yellow-700 text-sm mt-1">
                                            Для съёмки еды лучше открыть приложение на телефоне. На десктопе можно загрузить готовые фото.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}

                        <UploadDropzone onFilesSelected={handleFilesSelected} maxFiles={AI_LIMITS.MAX_PHOTOS_PER_UPLOAD} isDesktop={isDesktop} />

                        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
                            <p className="text-blue-800 text-sm text-center">
                                {isDesktop
                                    ? '💡 Загрузите фото еды с хорошим освещением для точного распознавания'
                                    : '💡 Для лучшего результата сфотографируйте еду сверху при хорошем освещении'}
                            </p>
                        </div>

                        {error && (
                            <div className="bg-red-50 border border-red-200 rounded-2xl p-4 mt-4">
                                <p className="text-red-600 text-center font-medium">{error}</p>
                            </div>
                        )}
                    </div>
                )}

                {showLimitModal && (
                    <LimitReachedModal
                        dailyLimit={billing.data?.daily_photo_limit || 3}
                        onClose={() => {
                            setShowLimitModal(false);
                            navigate('/');
                        }}
                        onUpgrade={() => navigate('/subscription')}
                    />
                )}

                {showBatchResults && (
                    <BatchResultsModal
                        photoQueue={photoQueue}
                        onRetry={(id) => {
                            setShowBatchResults(false);
                            retryPhoto(id);
                        }}
                        onRetryAll={() => {
                            setShowBatchResults(false);
                            photoQueue.forEach((p) => {
                                if (p.status === 'error') retryPhoto(p.id);
                            });
                        }}
                        onClose={handleCloseResults}
                        onRemove={removePhoto}
                        onBackToCamera={() => {
                            setShowBatchResults(false);
                            cleanup();
                            // Stay on camera page
                        }}
                    />
                )}

                {billing.data && !billing.loading && (
                    <div
                        className={`mt-8 rounded-xl p-3 text-sm ${billing.isPro ? 'bg-purple-50 border border-purple-100' : billing.isLimitReached ? 'bg-red-50 border border-red-100' : 'bg-blue-50 border border-blue-100'
                            }`}
                    >
                        {billing.isPro ? (
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <Check className="text-purple-600" size={16} />
                                    <span className="font-medium text-purple-900">PRO активен</span>
                                </div>
                                {billing.data.expires_at && (
                                    <span className="text-purple-600 text-xs">
                                        до {new Date(billing.data.expires_at).toLocaleDateString('ru-RU')}
                                    </span>
                                )}
                            </div>
                        ) : billing.isLimitReached ? (
                            <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                    <AlertCircle className="text-red-600" size={16} />
                                    <span className="font-medium text-red-900">Лимит исчерпан</span>
                                </div>
                                <button onClick={() => navigate('/subscription')} className="text-red-600 font-medium text-xs hover:underline whitespace-nowrap">
                                    Купить PRO
                                </button>
                            </div>
                        ) : (
                            <div className="flex items-center justify-between">
                                <span className="text-blue-900">
                                    {billing.data.used_today} / {billing.data.daily_photo_limit} фото
                                </span>
                                <button onClick={() => navigate('/subscription')} className="text-blue-600 font-medium text-xs hover:underline">
                                    Увеличить лимит
                                </button>
                            </div>
                        )}
                    </div>
                )}
            </div>
        </div>
    );
};

export default FoodLogPage;
