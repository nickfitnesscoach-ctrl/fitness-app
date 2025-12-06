import React, { useState, useRef } from 'react';
import { Camera, CreditCard, AlertCircle, Check, X, Send } from 'lucide-react';
import { api } from '../services/api';
import { useNavigate, useLocation } from 'react-router-dom';
import { useBilling } from '../contexts/BillingContext';
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';
import { BatchResultsModal, BatchResult, AnalysisResult } from '../components/BatchResultsModal';
import { POLLING, getErrorMessage, API_ERROR_CODES } from '../constants';

// Polling constants (from centralized config)
const POLLING_MAX_DURATION = POLLING.MAX_DURATION_MS;
const POLLING_INITIAL_DELAY = POLLING.INITIAL_DELAY_MS;
const POLLING_MAX_DELAY = POLLING.MAX_DELAY_MS;
const POLLING_BACKOFF_MULTIPLIER = POLLING.BACKOFF_MULTIPLIER;

const FoodLogPage: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const billing = useBilling();
    const { isReady, isTelegramWebApp: webAppDetected, isDesktop } = useTelegramWebApp();

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

    // For async polling cancellation
    const pollingAbortRef = useRef<AbortController | null>(null);

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



    /**
     * Poll task status until completion or timeout
     * 
     * Backend returns on SUCCESS:
     * {
     *   state: "SUCCESS",
     *   result: {
     *     success: true/false,
     *     meal_id: "...",
     *     recognized_items: [...],
     *     totals: { calories, protein, fat, carbohydrates },
     *     error?: "..." (when success: false)
     *   }
     * }
     */
    const pollTaskStatus = async (taskId: string, abortController: AbortController): Promise<AnalysisResult | null> => {
        const startTime = Date.now();
        let attempt = 0;

        while (!abortController.signal.aborted) {
            const elapsed = Date.now() - startTime;
            if (elapsed >= POLLING_MAX_DURATION) {
                const timeoutError = new Error('Превышено время ожидания распознавания');
                (timeoutError as any).errorType = 'TIMEOUT';
                throw timeoutError;
            }

            const delay = Math.min(
                POLLING_INITIAL_DELAY * Math.pow(POLLING_BACKOFF_MULTIPLIER, attempt),
                POLLING_MAX_DELAY
            );

            try {
                const taskStatus = await api.getTaskStatus(taskId);
                console.log(`[Polling] Task ${taskId} state: ${taskStatus.state}`, taskStatus);

                if (taskStatus.state === 'SUCCESS') {
                    const result = taskStatus.result;

                    // Backend may return success: false with error message
                    if (result && result.success === false) {
                        const emptyError = new Error(result.error || 'AI не смог распознать еду на фото');
                        (emptyError as any).errorType = 'AI_EMPTY_RESULT';
                        throw emptyError;
                    }

                    // Extract data from task result
                    let recognizedItems = result?.recognized_items || [];
                    const totals = result?.totals;
                    const mealId = result?.meal_id;

                    // FALLBACK: If recognized_items is empty but meal_id exists,
                    // fetch meal directly from API (items may have been saved but not returned)
                    if (recognizedItems.length === 0 && mealId) {
                        console.log(`[Polling] Empty recognized_items but meal_id=${mealId} exists. Waiting 1s before fallback fetch...`);

                        // Add 1s delay to allow DB commit/propagation
                        await new Promise(resolve => setTimeout(resolve, 1000));

                        try {
                            const mealData = await api.getMealAnalysis(mealId);
                            if (mealData.recognized_items && mealData.recognized_items.length > 0) {
                                console.log(`[Polling] Fallback successful: found ${mealData.recognized_items.length} items in meal`);
                                // Map from MealAnalysis format to AnalysisResult format
                                // Backend returns: id, name, grams, calories, protein, fat, carbohydrates
                                recognizedItems = mealData.recognized_items.map(item => ({
                                    id: String(item.id),
                                    name: item.name,
                                    grams: item.grams,
                                    calories: item.calories,
                                    protein: item.protein,
                                    fat: item.fat,
                                    carbohydrates: item.carbohydrates
                                }));
                            } else {
                                console.warn('[Polling] Fallback fetch returned 0 items');
                            }
                        } catch (fallbackErr) {
                            console.warn(`[Polling] Fallback fetch failed:`, fallbackErr);
                            // Continue with empty items - will show error below
                        }
                    }

                    // Calculate totals from items if not provided
                    const finalTotals = totals || {
                        calories: recognizedItems.reduce((sum, i) => sum + (i.calories || 0), 0),
                        protein: recognizedItems.reduce((sum, i) => sum + (i.protein || 0), 0),
                        fat: recognizedItems.reduce((sum, i) => sum + (i.fat || 0), 0),
                        carbohydrates: recognizedItems.reduce((sum, i) => sum + (i.carbohydrates || 0), 0)
                    };

                    return {
                        recognized_items: recognizedItems,
                        total_calories: finalTotals.calories || 0,
                        total_protein: finalTotals.protein || 0,
                        total_fat: finalTotals.fat || 0,
                        total_carbohydrates: finalTotals.carbohydrates || 0,
                        meal_id: mealId,
                        photo_url: result?.photo_url
                    };
                }

                if (taskStatus.state === 'FAILURE') {
                    const failError = new Error(taskStatus.error || 'Ошибка обработки фото');
                    (failError as any).errorType = 'CELERY_FAILURE';
                    throw failError;
                }

                // Task still processing (PENDING, STARTED, RETRY) - wait and retry
                await new Promise(resolve => setTimeout(resolve, delay));
                attempt++;

            } catch (err: any) {
                if (abortController.signal.aborted) {
                    return null;
                }

                // If it's our custom error, re-throw it
                if (err.errorType) {
                    throw err;
                }

                // Network error - retry a few times
                if (attempt < 3) {
                    console.warn(`[Polling] Network error, retry ${attempt + 1}/3:`, err.message);
                    await new Promise(resolve => setTimeout(resolve, delay));
                    attempt++;
                    continue;
                }

                const networkError = new Error('Ошибка сети при получении результата');
                (networkError as any).errorType = 'NETWORK_ERROR';
                throw networkError;
            }
        }

        return null; // Aborted
    };

    const processBatch = async (filesWithComments: FileWithComment[]) => {
        setIsBatchProcessing(true);
        setBatchProgress({ current: 0, total: filesWithComments.length });
        setBatchResults([]);
        setError(null);
        setCancelRequested(false);

        // Create abort controller for this batch
        const abortController = new AbortController();
        pollingAbortRef.current = abortController;

        const results: BatchResult[] = [];

        try {
            // Process files sequentially
            for (let i = 0; i < filesWithComments.length; i++) {
                // Check if user requested cancellation
                if (cancelRequested || abortController.signal.aborted) {
                    console.log('[Batch] User cancelled processing');
                    break;
                }

                const { file, comment } = filesWithComments[i];
                setBatchProgress({ current: i + 1, total: filesWithComments.length });

                try {
                    // Recognize with INDIVIDUAL comment per photo, selected meal type, and date
                    const dateStr = selectedDate.toISOString().split('T')[0]; // Format: YYYY-MM-DD
                    const recognizeResult = await api.recognizeFood(file, comment, mealType, dateStr);

                    let result: AnalysisResult;

                    // Check if async mode (HTTP 202)
                    if ((recognizeResult as any).isAsync && (recognizeResult as any).task_id) {
                        console.log(`[Batch] Async mode detected, polling task ${(recognizeResult as any).task_id}`);
                        const polledResult = await pollTaskStatus((recognizeResult as any).task_id, abortController);

                        if (!polledResult) {
                            // Polling was cancelled
                            break;
                        }
                        result = polledResult;
                    } else {
                        // Sync mode - result already contains recognized_items
                        result = recognizeResult as AnalysisResult;
                    }

                    // UNIVERSAL FALLBACK: If items empty but meal_id exists
                    // This handles BOTH Sync mode empty results AND Async results where pollTaskStatus fallback might have failed or not run
                    // We try one more time with a robust check here in `processBatch` loop
                    if ((!result.recognized_items || result.recognized_items.length === 0) && result.meal_id) {
                        console.log(`[Batch] Empty items but meal_id=${result.meal_id}, trying universal fallback...`);

                        // Add 1s delay for consistency
                        await new Promise(resolve => setTimeout(resolve, 1000));

                        try {
                            const mealData = await api.getMealAnalysis(result.meal_id);
                            if (mealData.recognized_items && mealData.recognized_items.length > 0) {
                                // Map from MealAnalysis format to AnalysisResult format
                                // Backend returns: id, name, grams, calories, protein, fat, carbohydrates
                                result.recognized_items = mealData.recognized_items.map(item => ({
                                    id: String(item.id),
                                    name: item.name,
                                    grams: item.grams,
                                    calories: item.calories,
                                    protein: item.protein,
                                    fat: item.fat,
                                    carbohydrates: item.carbohydrates
                                }));

                                // Recalculate totals
                                result.total_calories = result.recognized_items.reduce((sum: number, i) => sum + (i.calories || 0), 0);
                                result.total_protein = result.recognized_items.reduce((sum: number, i) => sum + (i.protein || 0), 0);
                                result.total_fat = result.recognized_items.reduce((sum: number, i) => sum + (i.fat || 0), 0);
                                result.total_carbohydrates = result.recognized_items.reduce((sum: number, i) => sum + (i.carbohydrates || 0), 0);
                            }
                        } catch (fallbackErr) {
                            console.warn(`[Batch] Universal fallback failed:`, fallbackErr);
                        }
                    }

                    if (result.recognized_items && result.recognized_items.length > 0) {
                        results.push({
                            file,
                            status: 'success',
                            data: result
                        });
                    } else {
                        // AI returned success but no items - AND fallback failed
                        // This implies the model really didn't find anything OR fallback fetch failed
                        console.warn(`[Batch] Final result empty for meal_id=${result.meal_id}. Status: ERROR`);
                        results.push({
                            file,
                            status: 'error',
                            error: 'Еда не распознана. Попробуйте сфотографировать блюдо ближе или при лучшем освещении.'
                        });
                    }
                } catch (err: any) {
                    console.error(`[Batch] Error processing file ${file.name}:`, err);
                    console.log(`[Batch] Error details: errorType=${err.errorType}, error=${err.error}, code=${err.code}`);

                    // Check for daily limit
                    if (err.error === API_ERROR_CODES.DAILY_LIMIT_REACHED || err.code === API_ERROR_CODES.DAILY_LIMIT_REACHED) {
                        setShowLimitModal(true);
                        results.push({
                            file,
                            status: 'error',
                            error: getErrorMessage(API_ERROR_CODES.DAILY_LIMIT_REACHED)
                        });
                        break;
                    }

                    // Determine error message using centralized localization
                    let errorMessage: string;

                    // Custom error types from pollTaskStatus
                    if (err.errorType === 'AI_EMPTY_RESULT') {
                        errorMessage = getErrorMessage('No food items recognized');
                    } else if (err.errorType === 'TIMEOUT') {
                        errorMessage = getErrorMessage(API_ERROR_CODES.TIMEOUT);
                    } else if (err.errorType === 'NETWORK_ERROR') {
                        errorMessage = getErrorMessage(API_ERROR_CODES.NETWORK_ERROR);
                    } else if (err.errorType === 'CELERY_FAILURE') {
                        errorMessage = getErrorMessage(API_ERROR_CODES.SERVER_ERROR);
                    } else if (err.error) {
                        // Use error code from backend
                        errorMessage = getErrorMessage(err.error, err.message);
                    } else if (err.message) {
                        // Try to localize error message
                        errorMessage = getErrorMessage(err.message);
                    } else {
                        errorMessage = getErrorMessage('default');
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
            pollingAbortRef.current = null;
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

                {/* Date and Meal Type Selector */}
                <div className="bg-white rounded-3xl shadow-sm p-4 mb-6">
                    <div className="grid grid-cols-2 gap-4">
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
                                    {mealTypeOptions.map((option) => (
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
                                    // Abort any ongoing polling
                                    if (pollingAbortRef.current) {
                                        pollingAbortRef.current.abort();
                                    }
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

                        {/* Desktop Warning */}
                        {isDesktop && (
                            <div className="bg-yellow-50 border border-yellow-200 rounded-2xl p-4">
                                <div className="flex items-start gap-3">
                                    <AlertCircle className="text-yellow-600 shrink-0 mt-0.5" size={20} />
                                    <div>
                                        <p className="text-yellow-800 font-medium text-sm">
                                            Вы используете десктоп-версию
                                        </p>
                                        <p className="text-yellow-700 text-sm mt-1">
                                            Для съёмки еды рекомендуем открыть приложение на телефоне.
                                            На десктопе можно загрузить готовые фото.
                                        </p>
                                    </div>
                                </div>
                            </div>
                        )}

                        <label className="block">
                            <div className="aspect-video bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 rounded-3xl flex flex-col items-center justify-center text-white shadow-xl active:scale-95 transition-transform cursor-pointer">
                                <Camera size={64} className="mb-4" />
                                <span className="text-xl font-bold mb-2">
                                    {isDesktop ? 'Загрузить фото' : 'Сфотографировать'}
                                </span>
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
                                {isDesktop
                                    ? '💡 Загрузите фото еды с хорошим освещением для точного распознавания'
                                    : '💡 Для лучшего результата сфотографируйте еду сверху при хорошем освещении'
                                }
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

                {/* Compact Billing Info Footer */}
                {billing.data && !billing.loading && (
                    <div className={`mt-8 rounded-xl p-3 text-sm ${billing.isPro
                        ? 'bg-purple-50 border border-purple-100'
                        : billing.isLimitReached
                            ? 'bg-red-50 border border-red-100'
                            : 'bg-blue-50 border border-blue-100'
                        }`}>
                        {billing.isPro ? (
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                    <Check className="text-purple-600" size={16} />
                                    <span className="font-medium text-purple-900">
                                        PRO активен
                                    </span>
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
                                    <span className="font-medium text-red-900">
                                        Лимит исчерпан
                                    </span>
                                </div>
                                <button
                                    onClick={() => navigate('/subscription')}
                                    className="text-red-600 font-medium text-xs hover:underline whitespace-nowrap"
                                >
                                    Купить PRO
                                </button>
                            </div>
                        ) : (
                            <div className="flex items-center justify-between">
                                <span className="text-blue-900">
                                    {billing.data.used_today} / {billing.data.daily_photo_limit} фото
                                </span>
                                <button
                                    onClick={() => navigate('/subscription')}
                                    className="text-blue-600 font-medium text-xs hover:underline"
                                >
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
