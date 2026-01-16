import React, { useState, useEffect } from 'react';
import { AlertCircle, Check, X, Send, Calendar as CalendarIcon, ChevronDown } from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { MEAL_TYPE_LABELS } from '../constants/meals';
import { useBilling } from '../contexts/BillingContext';
import { useAuth } from '../contexts/AuthContext';
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';
import { PageContainer } from '../components/shared/PageContainer';
import PageHeader from '../components/PageHeader';

import {
    SelectedPhotosList,
    BatchResultsModal,
    BatchProcessingScreen,
    LimitReachedModal,
    UploadDropzone,
    DebugPhotoControls,
    DebugStatusPanel,
    isHeicFile,
    convertHeicToJpeg,
    MEAL_TYPE_OPTIONS,
    AI_LIMITS,
    useAIProcessing,
    // P1.2: Unified status helpers
    isInFlightStatus,
    isResultStatus,
    isTerminalStatus,
} from '../features/ai';
import type { FileWithComment } from '../features/ai';
import { IS_DEBUG } from '../shared/config/debug';

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
    const [mealType, setMealType] = useState<string>((location.state as any)?.mealType || 'breakfast');
    const [selectedFiles, setSelectedFiles] = useState<FileWithComment[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [showLimitModal, setShowLimitModal] = useState(false);

    // DEBUG: Prevent auto-reopen after user manually closes the modal
    const userClosedResultsRef = React.useRef(false);

    // P0: Retry context from location state
    const retryMealId = (location.state as any)?.retryMealId;
    const retryMealPhotoId = (location.state as any)?.retryMealPhotoId;
    const isIphone = /iPhone|iPad|iPod/i.test(navigator.userAgent);

    const {
        photoQueue,
        showResults, // from context
        isProcessing,
        startBatch,
        retryPhoto,
        retrySelected,
        cancelBatch,
        cleanup,
        openResults,
        closeResults,
    } = useAIProcessing();

    // P1.2: Calculate inFlight/terminal using unified helpers
    const hasQueueInFlight = photoQueue.some(p => isInFlightStatus(p.status));
    const allDone = photoQueue.length > 0 && !hasQueueInFlight;
    // P1.2: hasAnyResult = success or error (things worth showing in results modal)
    const hasAnyResult = photoQueue.some(p => isResultStatus(p.status));
    // P1.2: hasAnyTerminal includes cancelled (for queue state checks)
    const hasAnyTerminal = photoQueue.some(p => isTerminalStatus(p.status));

    // Listen to global limit event if needed, or handle errors locally via context.
    useEffect(() => {
        const hasLimitError = photoQueue.some(p => p.errorCode === 'DAILY_LIMIT_REACHED');
        if (hasLimitError && !showLimitModal) {
            setShowLimitModal(true);
        }
    }, [photoQueue, showLimitModal]);

    // unmount cleanup: ONLY revoke local preview urls
    useEffect(() => {
        return () => {
            selectedFiles.forEach((f) => {
                if (f.previewUrl) URL.revokeObjectURL(f.previewUrl);
            });
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // P0 FIX: Auto-open results when queue reaches terminal state
    // Uses allDone + hasAnyResult (computed from queue statuses directly)
    // NOT dependent on isProcessing flag which can lag behind
    useEffect(() => {
        if (IS_DEBUG) {
            console.log('[FoodLogPage] Auto-open check:', {
                queueLength: photoQueue.length,
                allDone,
                hasAnyResult,
                hasAnyTerminal,
                hasQueueInFlight,
                showResults,
                statuses: photoQueue.map(p => p.status).join(','),
            });
        }

        // P1: Auto-open only if there are actual results (success/error)
        // Don't open for cancelled-only batches - nothing to show user
        if (!showResults && allDone && hasAnyResult && !userClosedResultsRef.current) {
            if (IS_DEBUG) console.log('[FoodLogPage] Opening results modal');
            openResults();
            // Clear selected files if any
            if (selectedFiles.length > 0) {
                setSelectedFiles([]);
            }
            // Refresh billing to update limits
            billing.refresh();
        }
    }, [showResults, allDone, hasAnyResult, hasAnyTerminal, hasQueueInFlight, photoQueue, openResults, selectedFiles, billing]);

    const buildFileWithComment = async (file: File): Promise<FileWithComment> => {
        if (isHeicFile(file)) {
            try {
                const converted = await convertHeicToJpeg(file);
                return { file: converted, comment: '', previewUrl: URL.createObjectURL(converted) };
            } catch {
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

        // Check if user has reached daily limit BEFORE starting batch
        // В debug режиме лимиты не проверяются — для тестирования AI-пайплайна
        if (!IS_DEBUG && !billing.isPro && billing.isLimitReached) {
            setShowLimitModal(true);
            return;
        }

        startBatch(selectedFiles, {
            date: selectedDate.toISOString().split('T')[0],
            mealType: mealType,
            mealId: retryMealId,
            mealPhotoId: retryMealPhotoId
        });

        // Reset "user closed" flag for new batch
        userClosedResultsRef.current = false;
        setSelectedFiles([]);
    };

    const handleCloseResults = () => {
        // P3: "Done" logic
        // 1. Check if there are ANY successes in the queue
        const hasAnySuccess = photoQueue.some(p => p.status === 'success');
        const dateStr = selectedDate.toISOString().split('T')[0];

        if (IS_DEBUG) {
            console.log('[FoodLogPage] handleCloseResults (Done):', { hasAnySuccess, queueLen: photoQueue.length });
        }

        if (hasAnySuccess) {
            // Case A: Partial or Full Success -> "Save" semantics
            // 1. Explicitly trigger diary refresh via URL (ClientDashboard listens to this)
            // 2. ONLY THEN perform cleanup (which is now safe and won't delete the meal)

            // We navigate with replace to avoid history stack issues, and set refresh=1
            navigate(`/?date=${dateStr}&refresh=1`, { replace: true });

            // Since we are navigating away, we can call cleanup. 
            // In a strict sense, we might want to wait for "refresh" confirmation, 
            // but the navigation unmounts this page anyway or switches focus. 
            // The critical part is that cleanup() DOES NOT DELETE the meal now.
            cleanup();
            closeResults();
        } else {
            // Case B: No successes (cancelled, error, or empty) -> "Discard" semantics
            // 1. Cleanup first (this WILL delete the orphan meal if it exists)
            cleanup();
            closeResults();
            // Just go back to diary without forced refresh (or with, doesn't matter much, but cleaner without)
            navigate(`/?date=${dateStr}`, { replace: true });
        }
    };

    const handleBackToCamera = () => {
        closeResults();
        // DEBUG: Don't cleanup - preserve queue state for inspection
        if (!IS_DEBUG) {
            cleanup();
        }
    };

    if (!isReady) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    if (!webAppDetected && !isBrowserDebug && !webAppBrowserDebug) {
        return (
            <div className="min-h-screen flex items-center justify-center p-4">
                <div className="bg-orange-50 border-2 border-orange-200 rounded-2xl p-6 text-center max-w-md">
                    <h2 className="text-xl font-bold text-orange-900 mb-2">Откройте через Telegram</h2>
                    <p className="text-orange-700">
                        Это приложение работает только внутри Telegram. Откройте бота и нажмите “Открыть приложение”.
                    </p>
                </div>
            </div>
        );
    }

    // P0 FIX: Show processing screen only when there are actual in-flight items
    // Not when queue has items but all are terminal (success/error)
    const showProcessing = hasQueueInFlight && !showResults;

    return (
        <div className="flex-1 bg-gradient-to-br from-blue-50 via-white to-purple-50">
            <PageHeader
                title={retryMealId ? `Повтор: ${MEAL_TYPE_LABELS[mealType] || mealType}` : 'Добавить еду'}
                fallbackRoute="/"
            />
            <PageContainer className="py-6 space-y-[var(--section-gap)]">
                {/* Date & Meal Type Selection Card */}
                <div className="bg-white rounded-[var(--radius-card)] shadow-sm p-[var(--card-p)] border border-gray-100">
                    <div className="grid grid-cols-1 gap-4">
                        {/* Date Selection */}
                        <div className="space-y-1.5">
                            <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
                                Дата
                            </label>
                            <div className="relative">
                                <input
                                    type="date"
                                    value={selectedDate.toISOString().split('T')[0]}
                                    onChange={(e) => setSelectedDate(new Date(e.target.value))}
                                    className="w-full h-[var(--tap-h)] px-4 pr-10 rounded-xl border border-gray-200 bg-gray-50 text-[16px] font-semibold text-gray-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all appearance-none"
                                />
                                <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none">
                                    <CalendarIcon size={18} className="text-gray-400" />
                                </div>
                            </div>
                        </div>

                        {/* Meal Type Selection */}
                        <div className="space-y-1.5">
                            <label className="block text-[10px] font-bold text-gray-400 uppercase tracking-widest ml-1">
                                Приём пищи
                            </label>
                            <div className="relative">
                                <select
                                    value={mealType}
                                    onChange={(e) => setMealType(e.target.value)}
                                    className="w-full h-[var(--tap-h)] px-4 pr-10 rounded-xl border border-gray-200 bg-gray-50 text-[16px] font-semibold text-gray-900 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 outline-none transition-all appearance-none"
                                >
                                    {MEAL_TYPE_OPTIONS.map((option) => (
                                        <option key={option.value} value={option.value}>
                                            {option.label}
                                        </option>
                                    ))}
                                </select>
                                <div className="absolute inset-y-0 right-3 flex items-center pointer-events-none text-gray-400">
                                    <ChevronDown size={20} />
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Debug Mode: Photo Controls + Status Panel */}
                {IS_DEBUG && (
                    <div className="space-y-4">
                        <DebugPhotoControls
                            selectedFiles={selectedFiles}
                            onFilesSelected={handleFilesSelected}
                            onClearFiles={clearSelectedFiles}
                            onAnalyze={handleAnalyze}
                            onCancel={cancelBatch}
                            isProcessing={isProcessing}
                            hasActiveQueue={hasQueueInFlight}
                            isLimitReached={false}
                        />
                        <DebugStatusPanel
                            photoQueue={photoQueue}
                            isProcessing={isProcessing}
                        />
                    </div>
                )}

                {showProcessing ? (
                    photoQueue.length > 0 ? (
                        <BatchProcessingScreen
                            photoQueue={photoQueue}
                            onRetry={retryPhoto}
                            onShowResults={openResults}
                            onCancel={cancelBatch}
                        />
                    ) : (
                        <div className="flex flex-col items-center justify-center py-12 space-y-4">
                            <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full"></div>
                            <p className="text-gray-600 font-medium">Подготовка фото...</p>
                        </div>
                    )
                ) : selectedFiles.length > 0 ? (
                    <div className="space-y-[var(--section-gap)] animate-in fade-in slide-in-from-bottom-4 duration-300">
                        <div className="bg-white rounded-[var(--radius-card)] p-[var(--card-p)] shadow-sm border border-gray-100">
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

                            {!billing.isPro && billing.isLimitReached ? (
                                <div className="mt-4 bg-red-50 border border-red-200 rounded-xl p-3">
                                    <p className="text-red-800 text-sm font-medium">
                                        ⚠️ <strong>Лимит исчерпан:</strong> Вы использовали все {billing.data?.daily_photo_limit} фото за сегодня.{' '}
                                        <button onClick={() => navigate('/subscription')} className="underline hover:no-underline">
                                            Купить PRO
                                        </button>
                                    </p>
                                </div>
                            ) : (
                                <div className="mt-4 bg-blue-50 border border-blue-200 rounded-xl p-3">
                                    <p className="text-blue-800 text-sm">
                                        💡 <strong>Совет:</strong> Комментарий к каждому фото повышает точность распознавания
                                    </p>
                                </div>
                            )}

                            <div className="mt-6 grid grid-cols-2 gap-3">
                                <button
                                    onClick={clearSelectedFiles}
                                    className="py-3 px-4 rounded-xl font-bold text-gray-600 bg-gray-100 hover:bg-gray-200 transition-colors"
                                >
                                    Отмена
                                </button>
                                <button
                                    onClick={handleAnalyze}
                                    disabled={!IS_DEBUG && !billing.isPro && billing.isLimitReached}
                                    className={`py-3 px-4 rounded-xl font-bold text-white transition-colors flex items-center justify-center gap-2 ${!IS_DEBUG && !billing.isPro && billing.isLimitReached
                                        ? 'bg-gray-400 cursor-not-allowed'
                                        : 'bg-blue-600 hover:bg-blue-700'
                                        }`}
                                >
                                    <Send size={18} />
                                    Отправить
                                </button>
                            </div>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-[var(--section-gap)]">
                        {isDesktop && (
                            <div className="bg-yellow-50 border border-yellow-200 rounded-[var(--radius-card)] p-[var(--card-p)]">
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

                        <div className="bg-blue-50 border border-blue-200 rounded-[var(--radius-card)] p-[var(--card-p)]">
                            <p className="text-blue-800 text-sm text-center">
                                {isDesktop
                                    ? '💡 Загрузите фото еды с хорошем освещением для точного распознавания'
                                    : isIphone
                                        ? '💡 Сфотографируйте еду сверху при хорошем освещении'
                                        : '💡 Загрузите фото из галереи или сфотографируйте еду'}
                            </p>
                        </div>

                        {error && (
                            <div className="bg-red-50 border border-red-200 rounded-[var(--radius-card)] p-[var(--card-p)] mt-4">
                                <p className="text-red-600 text-center font-medium">{error}</p>
                            </div>
                        )}
                    </div>
                )}

                {!IS_DEBUG && showLimitModal && (
                    <LimitReachedModal
                        isOpen={showLimitModal}
                        dailyLimit={billing.data?.daily_photo_limit || 3}
                        onClose={() => {
                            setShowLimitModal(false);
                            navigate('/');
                        }}
                        onUpgrade={() => navigate('/subscription')}
                    />
                )}

                {showResults && (
                    <BatchResultsModal
                        isOpen={showResults}
                        photoQueue={photoQueue}
                        onRetrySelected={(ids) => {
                            closeResults();
                            retrySelected(ids);
                        }}
                        onClose={handleCloseResults}
                        onBackToCamera={handleBackToCamera}
                    />
                )}

                {billing.data && !billing.loading && selectedFiles.length === 0 && !showProcessing && (
                    <div
                        className={`mt-4 rounded-[var(--radius-card)] p-[var(--card-p)] text-sm ${billing.isPro ? 'bg-purple-50 border border-purple-100' : billing.isLimitReached ? 'bg-red-50 border border-red-100' : 'bg-blue-50 border border-blue-100'
                            }`}
                    >
                        {billing.isPro ? (
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <Check className="text-purple-600" size={16} />
                                    <span className="font-medium text-purple-900">PRO активен</span>
                                </div>
                                {billing.data.expires_at && (
                                    <span className="text-purple-600 text-xs text-right">
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
            </PageContainer>
        </div>
    );
};

export default FoodLogPage;
