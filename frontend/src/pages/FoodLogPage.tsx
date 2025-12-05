import React, { useState } from 'react';
import { Camera, CreditCard, AlertCircle, Check, X, Send } from 'lucide-react';
import { api } from '../services/api';
import { useNavigate, useLocation } from 'react-router-dom';
import { useBilling } from '../contexts/BillingContext';
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';
import { BatchResultsModal, BatchResult, AnalysisResult } from '../components/BatchResultsModal';

const FoodLogPage: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const billing = useBilling();
    const { isReady, isTelegramWebApp: webAppDetected } = useTelegramWebApp();

    // Batch state
    const [isBatchProcessing, setIsBatchProcessing] = useState(false);
    const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 });
    const [batchResults, setBatchResults] = useState<BatchResult[]>([]);
    const [showBatchResults, setShowBatchResults] = useState(false);
    const [cancelRequested, setCancelRequested] = useState(false);

    // Preview state - now with individual comments per file
    interface FileWithComment {
        file: File;
        comment: string;
    }
    const [selectedFiles, setSelectedFiles] = useState<FileWithComment[]>([]);
    const [mealType, setMealType] = useState<string>('BREAKFAST');

    // Get initial date from location state or use today
    const getInitialDate = () => {
        const dateFromState = (location.state as any)?.selectedDate;
        if (dateFromState) {
            return new Date(dateFromState);
        }
        return new Date();
    };
    const [selectedDate, setSelectedDate] = useState<Date>(getInitialDate());

    const [error, setError] = useState<string | null>(null);
    const [showLimitModal, setShowLimitModal] = useState(false);

    const mealTypeOptions = [
        { value: 'BREAKFAST', label: 'Завтрак' },
        { value: 'LUNCH', label: 'Обед' },
        { value: 'DINNER', label: 'Ужин' },
        { value: 'SNACK', label: 'Перекус' },
    ];

    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        const files = event.target.files;
        if (files && files.length > 0) {
            let fileList = Array.from(files);

            // Limit to 5 files
            if (fileList.length > 5) {
                alert('За один раз можно загрузить не более 5 фото. Лишние фото будут проигнорированы.');
                fileList = fileList.slice(0, 5);
            }

            // Validate file sizes
            const validFiles = fileList.filter(file => {
                if (file.size > 10 * 1024 * 1024) {
                    console.warn(`File ${file.name} is too large (skipped)`);
                    return false;
                }
                return true;
            });

            if (validFiles.length === 0) {
                setError('Все выбранные файлы слишком большие (максимум 10MB).');
                return;
            }

            // Convert to FileWithComment objects with empty comments
            const filesWithComments: FileWithComment[] = validFiles.map(file => ({
                file,
                comment: ''
            }));
            setSelectedFiles(filesWithComments);
            setError(null);
        }
    };

    const handleRemoveFile = (index: number) => {
        const newFiles = [...selectedFiles];
        newFiles.splice(index, 1);
        setSelectedFiles(newFiles);
    };

    const handleCommentChange = (index: number, comment: string) => {
        const newFiles = [...selectedFiles];
        newFiles[index] = { ...newFiles[index], comment };
        setSelectedFiles(newFiles);
    };

    const handleAnalyze = () => {
        if (selectedFiles.length === 0) return;
        processBatch(selectedFiles);
    };



    const processBatch = async (filesWithComments: FileWithComment[]) => {
        setIsBatchProcessing(true);
        setBatchProgress({ current: 0, total: filesWithComments.length });
        setBatchResults([]);
        setError(null);
        setCancelRequested(false);

        const results: BatchResult[] = [];

        try {
            // Process files sequentially
            for (let i = 0; i < filesWithComments.length; i++) {
                // Check if user requested cancellation
                if (cancelRequested) {
                    console.log('[Batch] User cancelled processing');
                    break;
                }

                const { file, comment } = filesWithComments[i];
                setBatchProgress({ current: i + 1, total: filesWithComments.length });

                try {
                    // Recognize with INDIVIDUAL comment per photo, selected meal type, and date
                    const dateStr = selectedDate.toISOString().split('T')[0]; // Format: YYYY-MM-DD
                    const result = await api.recognizeFood(file, comment, mealType, dateStr) as AnalysisResult;

                    if (result.recognized_items && result.recognized_items.length > 0) {
                        results.push({
                            file,
                            status: 'success',
                            data: result
                        });
                    } else {
                        results.push({
                            file,
                            status: 'error',
                            error: 'Еда не найдена'
                        });
                    }
                } catch (err: any) {
                    console.error(`[Batch] Error processing file ${file.name}:`, err);

                    // Check for daily limit
                    if (err.error === 'DAILY_LIMIT_REACHED' || err.code === 'DAILY_LIMIT_REACHED') {
                        setShowLimitModal(true);
                        results.push({
                            file,
                            status: 'error',
                            error: 'Лимит исчерпан'
                        });
                        break;
                    }

                    // Show specific error message
                    let errorMessage = 'Ошибка распознавания';
                    if (err.message) {
                        if (err.message.includes('Failed to add food item')) {
                            errorMessage = 'Ошибка сохранения';
                        } else if (err.message.includes('timeout')) {
                            errorMessage = 'Превышено время ожидания';
                        } else if (err.message.includes('Network') || err.message.includes('fetch')) {
                            errorMessage = 'Ошибка сети';
                        }
                    }

                    results.push({
                        file,
                        status: 'error',
                        error: errorMessage
                    });
                }
            }

            setBatchResults(results);

            // Refresh billing info
            await billing.refresh();

            // Show results modal
            setShowBatchResults(true);

            // Clear selection
            setSelectedFiles([]);

        } catch (err: any) {
            console.error('[Batch] Global error:', err);
            setError('Произошла ошибка при обработке фотографий.');
        } finally {
            setIsBatchProcessing(false);
        }
    };

    const handleCloseResults = () => {
        setShowBatchResults(false);
        // Navigate back to dashboard with the selected date
        const dateStr = selectedDate.toISOString().split('T')[0];
        navigate(`/?date=${dateStr}`);
    };

    // While WebApp is initializing
    if (!isReady) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    // WebApp is ready but we're not in Telegram
    if (!webAppDetected) {
        return (
            <div className="min-h-screen flex items-center justify-center p-4">
                <div className="bg-orange-50 border-2 border-orange-200 rounded-2xl p-6 text-center max-w-md">
                    <h2 className="text-xl font-bold text-orange-900 mb-2">
                        Откройте через Telegram
                    </h2>
                    <p className="text-orange-700">
                        Это приложение работает только внутри Telegram.
                        Пожалуйста, откройте бота и нажмите кнопку "Открыть приложение".
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-4 pb-24">
            <div className="max-w-lg mx-auto">
                <h1 className="text-2xl font-bold text-gray-900 mb-4 text-center">Дневник питания</h1>

                {/* Billing Info Banner */}
                {billing.data && !billing.loading && (
                    <div className={`mb-6 rounded-2xl p-4 ${billing.isPro
                        ? 'bg-gradient-to-r from-purple-100 to-blue-100 border-2 border-purple-200'
                        : billing.isLimitReached
                            ? 'bg-red-50 border-2 border-red-200'
                            : 'bg-blue-50 border-2 border-blue-200'
                        }`}>
                        {billing.isPro ? (
                            <>
                                <div className="flex items-center gap-2 mb-1">
                                    <Check className="text-purple-600" size={18} />
                                    <span className="font-semibold text-purple-900">
                                        Ваш тариф: {billing.data.plan_name}
                                    </span>
                                </div>
                                <p className="text-purple-700 text-sm">
                                    Анализ фото — без ограничений ∞
                                </p>
                                {billing.data.expires_at && (
                                    <p className="text-purple-700 text-sm mt-1 font-medium">
                                        Подписка активна до {new Date(billing.data.expires_at).toLocaleDateString('ru-RU', {
                                            day: 'numeric',
                                            month: 'long',
                                            year: 'numeric'
                                        })}
                                    </p>
                                )}
                            </>
                        ) : billing.isLimitReached ? (
                            <>
                                <div className="flex items-center gap-2 mb-1">
                                    <AlertCircle className="text-red-600" size={18} />
                                    <span className="font-semibold text-red-900">
                                        Лимит на сегодня исчерпан
                                    </span>
                                </div>
                                <p className="text-red-700 text-sm mb-3">
                                    Использовано: {billing.data.used_today} из {billing.data.daily_photo_limit} фото
                                </p>
                                <button
                                    onClick={() => navigate('/subscription')}
                                    className="w-full bg-red-600 text-white py-2 rounded-xl font-medium hover:bg-red-700 transition-colors flex items-center justify-center gap-2"
                                >
                                    <CreditCard size={18} />
                                    Оформить PRO
                                </button>
                            </>
                        ) : (
                            <>
                                <div className="flex items-center justify-between mb-1">
                                    <span className="font-semibold text-blue-900">
                                        {billing.data.plan_name}
                                    </span>
                                    <button
                                        onClick={() => navigate('/subscription')}
                                        className="text-blue-600 text-sm font-medium hover:underline"
                                    >
                                        Обновить
                                    </button>
                                </div>
                                <p className="text-blue-700 text-sm">
                                    Сегодня: {billing.data.used_today} из {billing.data.daily_photo_limit} фото проанализировано
                                </p>
                            </>
                        )}
                    </div>
                )}

                {/* Date and Meal Type Selector */}
                <div className="bg-white rounded-3xl shadow-sm p-4 mb-6">
                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Дата приёма пищи</h3>
                    <input
                        type="date"
                        value={selectedDate.toISOString().split('T')[0]}
                        onChange={(e) => setSelectedDate(new Date(e.target.value))}
                        className="w-full p-3 rounded-xl border border-gray-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-200 outline-none transition-all mb-4"
                    />

                    <h3 className="text-sm font-semibold text-gray-700 mb-3">Тип приёма пищи</h3>
                    <div className="grid grid-cols-2 gap-3">
                        {mealTypeOptions.map((option) => (
                            <button
                                key={option.value}
                                onClick={() => setMealType(option.value)}
                                className={`py-3 px-4 rounded-xl font-bold transition-all ${
                                    mealType === option.value
                                        ? 'bg-gradient-to-br from-blue-500 to-purple-500 text-white shadow-lg scale-105'
                                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                                }`}
                            >
                                {option.label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Main Content Area */}
                {isBatchProcessing ? (
                    /* Batch Processing State */
                    <div className="space-y-6">
                        <div className="bg-white rounded-3xl p-8 shadow-lg text-center">
                            <div className="relative w-16 h-16 mx-auto mb-4">
                                <div className="absolute inset-0 border-4 border-gray-100 rounded-full"></div>
                                <div className="absolute inset-0 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                                <div className="absolute inset-0 flex items-center justify-center">
                                    <span className="text-sm font-bold text-blue-600">
                                        {batchProgress.current}/{batchProgress.total}
                                    </span>
                                </div>
                            </div>

                            <h3 className="text-xl font-bold text-gray-900 mb-2">
                                Обработка фотографий
                            </h3>
                            <p className="text-gray-600 font-medium">
                                Загружаю {batchProgress.current} из {batchProgress.total}...
                            </p>
                            <p className="text-gray-400 text-sm mt-4">
                                Пожалуйста, не закрывайте приложение
                            </p>

                            {/* Cancel Button */}
                            <button
                                onClick={() => {
                                    setCancelRequested(true);
                                    setIsBatchProcessing(false);
                                    setSelectedFiles([]);
                                }}
                                className="mt-6 w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-3 rounded-xl font-medium transition-colors"
                            >
                                Прекратить анализ
                            </button>
                        </div>
                    </div>
                ) : selectedFiles.length > 0 ? (
                    /* Preview State with Individual Comments */
                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
                        <div className="bg-white rounded-3xl p-6 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-lg font-bold text-gray-900">Выбранные фото ({selectedFiles.length})</h2>
                                <button
                                    onClick={() => setSelectedFiles([])}
                                    className="text-gray-400 hover:text-gray-600"
                                >
                                    <X size={20} />
                                </button>
                            </div>

                            {/* Vertical list of photos with individual comment fields */}
                            <div className="space-y-4">
                                {selectedFiles.map(({ file, comment }, index) => (
                                    <div key={index} className="bg-gray-50 rounded-2xl p-4 border border-gray-200">
                                        <div className="flex gap-4">
                                            {/* Photo Preview */}
                                            <div className="relative shrink-0 w-24 h-24 rounded-xl overflow-hidden group">
                                                <img
                                                    src={URL.createObjectURL(file)}
                                                    alt={`Preview ${index + 1}`}
                                                    className="w-full h-full object-cover"
                                                />
                                                <button
                                                    onClick={() => handleRemoveFile(index)}
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
                                                    onChange={(e) => handleCommentChange(index, e.target.value)}
                                                    placeholder={`Например: бургер 300 гр, картофель фри...`}
                                                    className="w-full bg-white border border-gray-300 rounded-xl p-3 text-sm text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all resize-none"
                                                    rows={3}
                                                />
                                            </div>
                                        </div>
                                    </div>
                                ))}

                                {/* Add More Button */}
                                {selectedFiles.length < 5 && (
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
                                            onChange={(e) => {
                                                if (e.target.files) {
                                                    const newFiles = Array.from(e.target.files);
                                                    if (selectedFiles.length + newFiles.length > 5) {
                                                        alert('Максимум 5 фото');
                                                        return;
                                                    }
                                                    const newFilesWithComments = newFiles.map(f => ({ file: f, comment: '' }));
                                                    setSelectedFiles([...selectedFiles, ...newFilesWithComments]);
                                                }
                                            }}
                                        />
                                    </label>
                                )}
                            </div>

                            {/* Hint */}
                            <div className="mt-4 bg-blue-50 border border-blue-200 rounded-xl p-3">
                                <p className="text-blue-800 text-sm">
                                    💡 <strong>Совет:</strong> Укажите комментарий для каждого фото отдельно — так ИИ точнее распознает блюда и калории
                                </p>
                            </div>

                            {/* Actions */}
                            <div className="mt-6 grid grid-cols-2 gap-3">
                                <button
                                    onClick={() => setSelectedFiles([])}
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
                    /* Initial Upload State */
                    <div className="space-y-6">
                        <p className="text-center text-gray-500 mb-4">
                            Выберите способ добавления фото
                        </p>

                        <label className="block">
                            <div className="aspect-video bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-3xl flex flex-col items-center justify-center text-white shadow-xl active:scale-95 transition-transform cursor-pointer">
                                <Camera size={64} className="mb-4" />
                                <span className="text-xl font-bold mb-2">Загрузить фото</span>
                                <span className="text-sm text-white/80">Можно выбрать до 5 фото</span>
                            </div>
                            <input
                                type="file"
                                accept="image/*"
                                multiple
                                className="hidden"
                                onChange={handleFileSelect}
                            />
                        </label>

                        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
                            <p className="text-blue-800 text-sm text-center">
                                💡 Для лучшего результата сфотографируйте еду сверху при хорошем освещении
                            </p>
                        </div>

                        {error && (
                            <div className="bg-red-50 border border-red-200 rounded-2xl p-4 mt-4">
                                <p className="text-red-600 text-center font-medium">{error}</p>
                            </div>
                        )}
                    </div>
                )}

                {/* Limit Reached Modal */}
                {showLimitModal && (
                    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
                        <div className="bg-white rounded-3xl p-6 max-w-sm w-full shadow-2xl">
                            <div className="text-center mb-4">
                                <AlertCircle className="text-red-500 mx-auto mb-3" size={48} />
                                <h3 className="text-xl font-bold text-gray-900 mb-2">
                                    Лимит исчерпан
                                </h3>
                                <p className="text-gray-600">
                                    Вы использовали свои {billing.data?.daily_photo_limit} бесплатных анализа.
                                    Некоторые фото не были обработаны.
                                </p>
                            </div>

                            <div className="space-y-3">
                                <button
                                    onClick={() => navigate('/subscription')}
                                    className="w-full bg-gradient-to-r from-blue-500 to-purple-500 text-white py-3 rounded-xl font-bold hover:from-blue-600 hover:to-purple-600 transition-colors flex items-center justify-center gap-2"
                                >
                                    <CreditCard size={20} />
                                    Оформить PRO
                                </button>
                                <button
                                    onClick={() => {
                                        setShowLimitModal(false);
                                        setIsBatchProcessing(false);
                                        navigate('/');
                                    }}
                                    className="w-full bg-gray-200 text-gray-700 py-3 rounded-xl font-medium hover:bg-gray-300 transition-colors"
                                >
                                    Понятно
                                </button>
                            </div>
                        </div>
                    </div>
                )}

                {/* Batch Results Modal */}
                {showBatchResults && (
                    <BatchResultsModal
                        results={batchResults}
                        onClose={handleCloseResults}
                        onOpenDiary={() => {
                            setShowBatchResults(false);
                            navigate('/');
                        }}
                    />
                )}
            </div>
        </div>
    );
};

export default FoodLogPage;
