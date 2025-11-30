import React, { useState } from 'react';
import { Camera, Upload, X, Check, Plus, CreditCard, AlertCircle } from 'lucide-react';
import { api, CreateMealRequest, CreateFoodItemRequest } from '../services/api';
import { useNavigate } from 'react-router-dom';
import { useBilling } from '../contexts/BillingContext';
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';

interface RecognizedItem {
    name: string;
    grams: number;
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

interface AnalysisResult {
    recognized_items: RecognizedItem[];
    total_calories: number;
    total_protein: number;
    total_fat: number;
    total_carbohydrates: number;
}

const FoodLogPage: React.FC = () => {
    const navigate = useNavigate();
    const billing = useBilling();
    const { isReady, isTelegramWebApp: webAppDetected } = useTelegramWebApp();
    const [selectedImage, setSelectedImage] = useState<string | null>(null);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [analysisResult, setAnalysisResult] = useState<AnalysisResult | null>(null);
    const [selectedItems, setSelectedItems] = useState<Set<number>>(new Set());
    const [error, setError] = useState<string | null>(null);
    const [errorCode, setErrorCode] = useState<string | null>(null);
    const [saving, setSaving] = useState(false);
    const [retryCount, setRetryCount] = useState(0);
    const [showLimitModal, setShowLimitModal] = useState(false);
    const MAX_RETRIES = 3;

    const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (file) {
            // Validate file size (max 10MB)
            if (file.size > 10 * 1024 * 1024) {
                setError('Файл слишком большой. Максимум 10MB.');
                return;
            }

            const reader = new FileReader();
            reader.onloadend = () => {
                const base64 = reader.result as string;
                setSelectedImage(base64);
                setSelectedFile(file);
                analyzeImage(file);
            };
            reader.readAsDataURL(file);
        }
    };

    const getErrorMessage = (errorCode: string, defaultMessage: string): string => {
        const messages: Record<string, string> = {
            'INVALID_IMAGE': 'Некорректное изображение. Попробуйте другое фото с едой',
            'MISSING_IMAGE': 'Изображение не выбрано. Попробуйте снова',
            'AI_SERVICE_ERROR': 'Сервис распознавания временно недоступен',
            'RATE_LIMIT_EXCEEDED': 'Слишком много запросов. Подождите минуту',
            'UNAUTHORIZED': 'Сессия истекла. Откройте приложение заново из Telegram',
            'NO_FOOD_DETECTED': 'Мы не нашли на фото еду. Попробуйте сделать кадр ближе или при лучшем освещении'
        };
        return messages[errorCode] || defaultMessage;
    };

    const analyzeImage = async (imageFile: File) => {
        setAnalyzing(true);
        setError(null);
        setErrorCode(null);
        setAnalysisResult(null);

        try {
            const result = await api.recognizeFood(imageFile);
            console.log('analysisResult received from API:', result);

            if (result.recognized_items && result.recognized_items.length > 0) {
                setAnalysisResult(result);
                console.log('analysisResult SET IN STATE:', result);
                setRetryCount(0); // Reset retry count on success
                // Select all items by default
                setSelectedItems(new Set(result.recognized_items.map((_: any, i: number) => i)));

                // Обновляем billing данные после успешного анализа
                await billing.refresh();
            } else {
                // Empty result - no food detected
                console.log('NO FOOD DETECTED - empty items array');
                setErrorCode('NO_FOOD_DETECTED');
                setError('Мы не нашли на фото еду. Попробуйте сделать кадр ближе или при лучшем освещении');
            }
        } catch (err: any) {
            console.error('Analysis failed:', err);
            const code = err.error || 'UNKNOWN_ERROR';
            setErrorCode(code);

            // Обработка DAILY_LIMIT_REACHED
            if (code === 'DAILY_LIMIT_REACHED') {
                setShowLimitModal(true);
                // Обновляем billing данные, чтобы счетчик обновился
                await billing.refresh();
            } else {
                setError(getErrorMessage(code, err.message || 'Ошибка при анализе фото'));
            }
        } finally {
            setAnalyzing(false);
        }
    };

    const toggleItemSelection = (index: number) => {
        const newSelected = new Set(selectedItems);
        if (newSelected.has(index)) {
            newSelected.delete(index);
        } else {
            newSelected.add(index);
        }
        setSelectedItems(newSelected);
    };

    const getMealTypeByTime = (): 'BREAKFAST' | 'LUNCH' | 'DINNER' | 'SNACK' => {
        const hour = new Date().getHours();
        if (hour >= 5 && hour < 11) return 'BREAKFAST';
        if (hour >= 11 && hour < 16) return 'LUNCH';
        if (hour >= 16 && hour < 22) return 'DINNER';
        return 'SNACK';
    };

    const getMealTypeLabel = (type: string): string => {
        const labels: Record<string, string> = {
            'BREAKFAST': 'Завтрак',
            'LUNCH': 'Обед',
            'DINNER': 'Ужин',
            'SNACK': 'Перекус'
        };
        return labels[type] || type;
    };

    const getSelectedTotals = () => {
        if (!analysisResult) return { calories: 0, protein: 0, fat: 0, carbohydrates: 0 };

        let totals = { calories: 0, protein: 0, fat: 0, carbohydrates: 0 };

        analysisResult.recognized_items.forEach((item, index) => {
            // Не включаем строку "Итого" в подсчёт
            if (selectedItems.has(index) && !item.name.toLowerCase().includes('итого')) {
                totals.calories += item.calories;
                totals.protein += item.protein;
                totals.fat += item.fat;
                totals.carbohydrates += item.carbohydrates;
            }
        });

        return {
            calories: Math.round(totals.calories),
            protein: Math.round(totals.protein * 10) / 10,
            fat: Math.round(totals.fat * 10) / 10,
            carbohydrates: Math.round(totals.carbohydrates * 10) / 10
        };
    };

    const handleSaveMeal = async () => {
        if (!analysisResult || selectedItems.size === 0) {
            console.warn('Cannot save meal: no analysis result or no items selected');
            return;
        }

        setSaving(true);
        setError(null);

        try {
            console.log('[FoodLog] Starting meal save process...');

            // 1. Create Meal
            const mealData: CreateMealRequest = {
                date: new Date().toISOString().split('T')[0],
                meal_type: getMealTypeByTime()
            };
            console.log('[FoodLog] Creating meal:', mealData);
            const meal = await api.createMeal(mealData);
            console.log('[FoodLog] Meal created:', meal);

            // 2. Add selected Food Items
            const selectedFoodItems = analysisResult.recognized_items
                .filter((_, index) => selectedItems.has(index))
                // Фильтруем строку "Итого" - её не нужно сохранять
                .filter((item) => !item.name.toLowerCase().includes('итого'))
                .map((item): CreateFoodItemRequest => ({
                    name: item.name,
                    grams: item.grams,
                    calories: item.calories,
                    protein: item.protein,
                    fat: item.fat,
                    carbohydrates: item.carbohydrates
                }));

            console.log(`[FoodLog] Adding ${selectedFoodItems.length} food items to meal ${meal.id}...`);

            const promises = selectedFoodItems.map(item => api.addFoodItem(meal.id, item));
            const addedItems = await Promise.all(promises);

            console.log('[FoodLog] All food items added successfully:', addedItems);

            // Success - show message and redirect
            const tg = window.Telegram?.WebApp;
            if (tg?.showAlert) {
                tg.showAlert('Приём пищи сохранён!');
                navigate('/');
            } else {
                alert('Приём пищи сохранён!');
                navigate('/');
            }
        } catch (err: any) {
            console.error('[FoodLog] Save error:', err);
            const errorMessage = err.message || 'Ошибка при сохранении приёма пищи';
            setError(errorMessage);

            // Show error in Telegram alert if available
            const tg = window.Telegram?.WebApp;
            if (tg?.showAlert) {
                tg.showAlert(`Ошибка: ${errorMessage}`);
            }
        } finally {
            setSaving(false);
        }
    };

    const resetState = () => {
        setSelectedImage(null);
        setSelectedFile(null);
        setAnalysisResult(null);
        setSelectedItems(new Set());
        setError(null);
        setErrorCode(null);
        setRetryCount(0);
        setShowLimitModal(false);
    };

    const retryAnalysis = () => {
        if (!selectedFile) return;

        if (retryCount >= MAX_RETRIES) {
            setError('Превышено количество попыток. Попробуйте загрузить другое фото');
            setErrorCode('MAX_RETRIES_EXCEEDED');
            return;
        }

        setRetryCount(prev => prev + 1);
        analyzeImage(selectedFile);
    };

    // Determine if retry button should be shown
    const canRetry = () => {
        if (!errorCode) return false;
        // Allow retry for service errors and empty results, but not for invalid image or auth errors
        return ['AI_SERVICE_ERROR', 'NO_FOOD_DETECTED', 'RATE_LIMIT_EXCEEDED'].includes(errorCode);
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

                {!selectedImage && !analysisResult ? (
                    /* Initial state - show capture options */
                    <div className="space-y-6">
                        <p className="text-center text-gray-500">
                            Сфотографируйте или загрузите фото еды для анализа
                        </p>

                        <div className="grid grid-cols-2 gap-4">
                            <label className="aspect-square bg-gradient-to-br from-blue-500 to-blue-600 rounded-3xl flex flex-col items-center justify-center text-white shadow-lg active:scale-95 transition-transform cursor-pointer">
                                <Camera size={48} className="mb-3" />
                                <span className="font-semibold">Камера</span>
                                <input
                                    type="file"
                                    accept="image/*;capture=camera"
                                    className="hidden"
                                    onChange={handleFileSelect}
                                />
                            </label>

                            <label className="aspect-square bg-gradient-to-br from-green-500 to-green-600 rounded-3xl flex flex-col items-center justify-center text-white shadow-lg active:scale-95 transition-transform cursor-pointer">
                                <Upload size={48} className="mb-3" />
                                <span className="font-semibold">Галерея</span>
                                <input
                                    type="file"
                                    accept="image/*"
                                    className="hidden"
                                    onChange={handleFileSelect}
                                />
                            </label>
                        </div>

                        <div className="bg-blue-50 border border-blue-200 rounded-2xl p-4">
                            <p className="text-blue-800 text-sm text-center">
                                💡 Для лучшего результата сфотографируйте еду сверху при хорошем освещении
                            </p>
                        </div>
                    </div>
                ) : (
                    /* Image selected or analyzing */
                    <div className="space-y-6">
                        {/* Image preview */}
                        <div className="relative rounded-3xl overflow-hidden shadow-xl">
                            <img
                                src={selectedImage || ''}
                                alt="Food"
                                className="w-full h-64 object-cover"
                            />
                            <button
                                onClick={resetState}
                                className="absolute top-3 right-3 bg-black/60 text-white p-2 rounded-full hover:bg-black/80 transition-colors"
                            >
                                <X size={24} />
                            </button>

                            {/* Meal type badge */}
                            <div className="absolute bottom-3 left-3 bg-white/90 backdrop-blur-sm px-3 py-1.5 rounded-full">
                                <span className="text-sm font-medium text-gray-800">
                                    {getMealTypeLabel(getMealTypeByTime())}
                                </span>
                            </div>
                        </div>

                        {/* Error message */}
                        {error && !showLimitModal && (
                            <div className="bg-red-50 border border-red-200 rounded-2xl p-4">
                                <p className="text-red-600 text-center font-medium">{error}</p>

                                {retryCount > 0 && retryCount < MAX_RETRIES && (
                                    <p className="text-red-500 text-sm text-center mt-2">
                                        Попытка {retryCount} из {MAX_RETRIES}
                                    </p>
                                )}

                                <div className="flex gap-2 mt-3">
                                    {canRetry() && retryCount < MAX_RETRIES && (
                                        <button
                                            onClick={retryAnalysis}
                                            disabled={analyzing}
                                            className="flex-1 bg-red-500 text-white py-2 rounded-xl font-medium hover:bg-red-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
                                        >
                                            {analyzing ? 'Анализируем...' : 'Попробовать снова'}
                                        </button>
                                    )}

                                    {(errorCode === 'NO_FOOD_DETECTED' || errorCode === 'INVALID_IMAGE' || errorCode === 'MISSING_IMAGE' || retryCount >= MAX_RETRIES) && (
                                        <button
                                            onClick={resetState}
                                            className="flex-1 bg-gray-500 text-white py-2 rounded-xl font-medium hover:bg-gray-600 transition-colors"
                                        >
                                            Выбрать другое фото
                                        </button>
                                    )}
                                </div>
                            </div>
                        )}

                        {/* Limit Reached Modal */}
                        {showLimitModal && (
                            <div className="bg-gradient-to-br from-orange-50 to-red-50 border-2 border-red-300 rounded-3xl p-6 shadow-xl">
                                <div className="text-center mb-4">
                                    <AlertCircle className="text-red-500 mx-auto mb-3" size={48} />
                                    <h3 className="text-xl font-bold text-gray-900 mb-2">
                                        Лимит бесплатных фото на сегодня исчерпан
                                    </h3>
                                    <p className="text-gray-600">
                                        Вы использовали свои {billing.data?.daily_photo_limit} бесплатных анализа.
                                        Подключите PRO, чтобы отправлять фото без ограничений.
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
                                        onClick={resetState}
                                        className="w-full bg-gray-200 text-gray-700 py-3 rounded-xl font-medium hover:bg-gray-300 transition-colors"
                                    >
                                        Позже
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Analyzing state */}
                        {analyzing && (
                            <div className="bg-white rounded-3xl p-8 shadow-lg text-center">
                                <div className="animate-spin w-12 h-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
                                <p className="text-gray-600 font-medium">Анализируем фото...</p>
                                <p className="text-gray-400 text-sm mt-2">Это может занять несколько секунд</p>
                            </div>
                        )}

                        {/* Results */}
                        {analysisResult && !analyzing && (
                            <div className="space-y-4">
                                {/* Items list */}
                                <div className="bg-white rounded-3xl p-5 shadow-lg">
                                    <h2 className="text-lg font-bold text-gray-900 mb-4">
                                        Распознанные блюда ({analysisResult.recognized_items.length})
                                    </h2>

                                    <div className="space-y-3">
                                        {analysisResult.recognized_items.map((item, index) => (
                                            <div
                                                key={index}
                                                onClick={() => toggleItemSelection(index)}
                                                className={`p-4 rounded-2xl border-2 cursor-pointer transition-all ${selectedItems.has(index)
                                                    ? 'border-blue-500 bg-blue-50'
                                                    : 'border-gray-200 bg-gray-50'
                                                    }`}
                                            >
                                                <div className="flex items-start justify-between">
                                                    <div className="flex-1">
                                                        <p className="font-semibold text-gray-900">{item.name}</p>
                                                        <p className="text-sm text-gray-500">{item.grams}г</p>
                                                    </div>
                                                    <div className="flex items-center gap-3">
                                                        <span className="font-bold text-orange-600">
                                                            {Math.round(item.calories)} ккал
                                                        </span>
                                                        <div className={`w-6 h-6 rounded-full flex items-center justify-center ${selectedItems.has(index)
                                                            ? 'bg-blue-500 text-white'
                                                            : 'bg-gray-200 text-gray-400'
                                                            }`}>
                                                            {selectedItems.has(index) ? <Check size={16} /> : <Plus size={16} />}
                                                        </div>
                                                    </div>
                                                </div>

                                                {/* Mini macros */}
                                                <div className="flex gap-4 mt-2 text-xs text-gray-500">
                                                    <span>Б: {item.protein.toFixed(1)}г</span>
                                                    <span>Ж: {item.fat.toFixed(1)}г</span>
                                                    <span>У: {item.carbohydrates.toFixed(1)}г</span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                </div>

                                {/* Totals */}
                                {selectedItems.size > 0 && (
                                    <div className="bg-gradient-to-br from-orange-500 to-red-500 rounded-3xl p-5 text-white">
                                        <p className="text-white/80 text-sm mb-2">Итого выбрано:</p>
                                        <div className="flex items-baseline gap-2 mb-3">
                                            <span className="text-3xl font-bold">{getSelectedTotals().calories}</span>
                                            <span className="text-white/80">ккал</span>
                                        </div>
                                        <div className="grid grid-cols-3 gap-2 text-sm">
                                            <div className="bg-white/20 rounded-xl p-2 text-center">
                                                <p className="text-white/70">Белки</p>
                                                <p className="font-bold">{getSelectedTotals().protein}г</p>
                                            </div>
                                            <div className="bg-white/20 rounded-xl p-2 text-center">
                                                <p className="text-white/70">Жиры</p>
                                                <p className="font-bold">{getSelectedTotals().fat}г</p>
                                            </div>
                                            <div className="bg-white/20 rounded-xl p-2 text-center">
                                                <p className="text-white/70">Углеводы</p>
                                                <p className="font-bold">{getSelectedTotals().carbohydrates}г</p>
                                            </div>
                                        </div>
                                    </div>
                                )}

                                {/* Save error display */}
                                {error && !analyzing && (
                                    <div className="bg-red-50 border border-red-200 rounded-2xl p-4">
                                        <p className="text-red-600 text-center font-medium">{error}</p>
                                    </div>
                                )}

                                {/* Save button */}
                                <button
                                    onClick={handleSaveMeal}
                                    disabled={selectedItems.size === 0 || saving}
                                    className={`w-full py-4 rounded-2xl font-bold flex items-center justify-center gap-2 transition-all ${selectedItems.size === 0 || saving
                                        ? 'bg-gray-200 text-gray-400 cursor-not-allowed'
                                        : 'bg-gradient-to-r from-green-500 to-emerald-500 text-white shadow-lg active:scale-95'
                                        }`}
                                >
                                    {saving ? (
                                        <>
                                            <div className="animate-spin w-5 h-5 border-2 border-white border-t-transparent rounded-full"></div>
                                            <span>Сохраняем...</span>
                                        </>
                                    ) : (
                                        <>
                                            <Check size={24} />
                                            <span>Добавить в дневник</span>
                                        </>
                                    )}
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
