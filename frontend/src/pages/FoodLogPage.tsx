import React, { useState } from 'react';
import { Camera, Upload, CreditCard, AlertCircle, Check, X, Send } from 'lucide-react';
import { api, CreateMealRequest } from '../services/api';
import { useNavigate } from 'react-router-dom';
import { useBilling } from '../contexts/BillingContext';
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';
import { isIOS } from '../utils/platform';
import { BatchResultsModal, BatchResult, AnalysisResult, RecognizedItem } from '../components/BatchResultsModal';

const FoodLogPage: React.FC = () => {
    const navigate = useNavigate();
    const billing = useBilling();
    const { isReady, isTelegramWebApp: webAppDetected } = useTelegramWebApp();

    // Batch state
    const [isBatchProcessing, setIsBatchProcessing] = useState(false);
    const [batchProgress, setBatchProgress] = useState({ current: 0, total: 0 });
    const [batchResults, setBatchResults] = useState<BatchResult[]>([]);
    const [showBatchResults, setShowBatchResults] = useState(false);
    const [createdMealId, setCreatedMealId] = useState<number | null>(null);

    // Preview state
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [description, setDescription] = useState('');

    const [error, setError] = useState<string | null>(null);
    const [showLimitModal, setShowLimitModal] = useState(false);

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

            // Instead of processing immediately, set selected files for preview
            setSelectedFiles(validFiles);
            setError(null);
        }
    };

    const handleRemoveFile = (index: number) => {
        const newFiles = [...selectedFiles];
        newFiles.splice(index, 1);
        setSelectedFiles(newFiles);
    };

    const handleAnalyze = () => {
        if (selectedFiles.length === 0) return;
        processBatch(selectedFiles, description);
    };

    const getMealTypeByTime = (): 'BREAKFAST' | 'LUNCH' | 'DINNER' | 'SNACK' => {
        const hour = new Date().getHours();
        if (hour >= 5 && hour < 11) return 'BREAKFAST';
        if (hour >= 11 && hour < 16) return 'LUNCH';
        if (hour >= 16 && hour < 22) return 'DINNER';
        return 'SNACK';
    };

    const processBatch = async (files: File[], desc: string) => {
        setIsBatchProcessing(true);
        setBatchProgress({ current: 0, total: files.length });
        setBatchResults([]);
        setError(null);

        const results: BatchResult[] = [];

        try {
            // 1. Create a meal upfront to add items to
            const mealData: CreateMealRequest = {
                date: new Date().toISOString().split('T')[0],
                meal_type: getMealTypeByTime()
            };
            const meal = await api.createMeal(mealData);
            console.log('[Batch] Meal created:', meal.id);
            setCreatedMealId(meal.id);

            // 2. Process files sequentially
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                setBatchProgress({ current: i + 1, total: files.length });

                try {
                    // Recognize with description
                    const result = await api.recognizeFood(file, desc) as AnalysisResult;

                    if (result.recognized_items && result.recognized_items.length > 0) {
                        // Filter out "Total" row if present
                        const itemsToAdd = result.recognized_items.filter((item: RecognizedItem) => !item.name.toLowerCase().includes('итого'));

                        // Add items to meal
                        for (const item of itemsToAdd) {
                            await api.addFoodItem(meal.id, {
                                name: item.name,
                                grams: item.grams,
                                calories: item.calories,
                                protein: item.protein,
                                fat: item.fat,
                                carbohydrates: item.carbohydrates
                            });
                        }

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
            setDescription('');

        } catch (err: any) {
            console.error('[Batch] Global error:', err);
            setError('Произошла ошибка при обработке фотографий.');
        } finally {
            setIsBatchProcessing(false);
        }
    };

    const handleCloseResults = () => {
        setShowBatchResults(false);
        navigate('/');
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
                        </div>
                    </div>
                ) : selectedFiles.length > 0 ? (
                    /* Preview State */
                    <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-300">
                        <div className="bg-white rounded-3xl p-6 shadow-sm">
                            <div className="flex items-center justify-between mb-4">
                                <h2 className="text-lg font-bold text-gray-900">Выбранные фото</h2>
                                <button
                                    onClick={() => setSelectedFiles([])}
                                    className="text-gray-400 hover:text-gray-600"
                                >
                                    <X size={20} />
                                </button>
                            </div>

                            {/* Horizontal scroll for photos */}
                            <div className="flex gap-3 overflow-x-auto pb-2 -mx-2 px-2 scrollbar-hide">
                                {selectedFiles.map((file, index) => (
                                    <div key={index} className="relative shrink-0 w-24 h-24 rounded-xl overflow-hidden group">
                                        <img
                                            src={URL.createObjectURL(file)}
                                            alt={`Preview ${index}`}
                                            className="w-full h-full object-cover"
                                        />
                                        <button
                                            onClick={() => handleRemoveFile(index)}
                                            className="absolute top-1 right-1 bg-black/50 text-white rounded-full p-1 opacity-0 group-hover:opacity-100 transition-opacity"
                                        >
                                            <X size={12} />
                                        </button>
                                    </div>
                                ))}
                                {selectedFiles.length < 5 && (
                                    <label className="shrink-0 w-24 h-24 rounded-xl border-2 border-dashed border-gray-200 flex flex-col items-center justify-center text-gray-400 hover:border-blue-400 hover:text-blue-500 transition-colors cursor-pointer">
                                        <Camera size={24} />
                                        <span className="text-xs mt-1">Добавить</span>
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
                                                    setSelectedFiles([...selectedFiles, ...newFiles]);
                                                }
                                            }}
                                        />
                                    </label>
                                )}
                            </div>

                            {/* Comment Input */}
                            <div className="mt-6">
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    Комментарий к еде (опционально)
                                </label>
                                <textarea
                                    value={description}
                                    onChange={(e) => setDescription(e.target.value)}
                                    placeholder="С комментарием анализ будет точнее. Пример: кура 150 гр, рис 200 гр..."
                                    className="w-full bg-gray-50 border border-gray-200 rounded-xl p-4 text-gray-900 placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all resize-none h-32"
                                />
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

                        {isIOS() && (
                            <>
                                <div className="relative">
                                    <div className="absolute inset-0 flex items-center">
                                        <div className="w-full border-t border-gray-300"></div>
                                    </div>
                                    <div className="relative flex justify-center text-sm">
                                        <span className="px-2 bg-gradient-to-br from-blue-50 via-white to-purple-50 text-gray-500">или</span>
                                    </div>
                                </div>

                                <button
                                    onClick={() => {
                                        const tg = window.Telegram?.WebApp;
                                        if (tg) {
                                            tg.openTelegramLink(`https://t.me/EatFit24Bot?startattach=photo`);
                                        }
                                    }}
                                    className="w-full aspect-video bg-gradient-to-br from-green-500 to-emerald-600 rounded-3xl flex flex-col items-center justify-center text-white shadow-xl active:scale-95 transition-transform"
                                >
                                    <Upload size={64} className="mb-4" />
                                    <span className="text-xl font-bold mb-2">Отправить в чате</span>
                                    <span className="text-sm text-white/80">Сфотографировать и отправить боту</span>
                                </button>
                            </>
                        )}

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
                        mealId={createdMealId}
                    />
                )}
            </div>
        </div>
    );
};

export default FoodLogPage;
