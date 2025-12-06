import React, { useEffect, useState } from 'react';
import { Flame, Drumstick, Droplets, Wheat, Plus, ChevronRight, Trash2 } from 'lucide-react';
import { useNavigate, useSearchParams, useLocation } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';

import Calendar from '../components/Calendar';
// F-019: Skeleton loaders for better loading UX
import { SkeletonDashboard } from '../components/Skeleton';
// F-033: Pull-to-refresh for mobile UX
import PullToRefresh from '../components/PullToRefresh';

interface DailyGoal {
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

interface TotalConsumed {
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

interface Meal {
    id: number;
    meal_type: string;
    date: string;
    food_items: any[];
}

const MEAL_TYPE_LABELS: Record<string, string> = {
    'BREAKFAST': 'Завтрак',
    'LUNCH': 'Обед',
    'DINNER': 'Ужин',
    'SNACK': 'Перекус'
};

const ClientDashboard: React.FC = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const { user, isBrowserDebug } = useAuth();
    const { isReady, isTelegramWebApp: webAppDetected, isBrowserDebug: webAppBrowserDebug } = useTelegramWebApp();
    const [searchParams, setSearchParams] = useSearchParams();

    const [loading, setLoading] = useState(true);
    const [goals, setGoals] = useState<DailyGoal | null>(null);
    const [consumed, setConsumed] = useState<TotalConsumed>({ calories: 0, protein: 0, fat: 0, carbohydrates: 0 });
    const [meals, setMeals] = useState<Meal[]>([]);
    const [error, setError] = useState<string | null>(null);

    // Get date from URL params or use today
    const getInitialDate = () => {
        const dateParam = searchParams.get('date');
        if (dateParam) {
            return new Date(dateParam);
        }
        return new Date();
    };
    const [selectedDate, setSelectedDate] = useState(getInitialDate());

    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [mealToDelete, setMealToDelete] = useState<number | null>(null);
    const [deleting, setDeleting] = useState(false);

    // Update URL when date changes
    useEffect(() => {
        const dateStr = selectedDate.toISOString().split('T')[0];
        setSearchParams({ date: dateStr }, { replace: true });
    }, [selectedDate]);

    // Reload data when navigating back to dashboard (location.key changes on each navigation)
    useEffect(() => {
        if (isReady && webAppDetected) {
            loadDashboardData(selectedDate);
        }
    }, [isReady, webAppDetected, selectedDate, location.key]);

    const loadDashboardData = async (date: Date) => {
        setLoading(true);
        setError(null);

        const dateStr = date.toISOString().split('T')[0];

        try {
            const goalsData = await api.getDailyGoals();
            if (goalsData && !goalsData.error) {
                setGoals({
                    calories: goalsData.calories || 2000,
                    protein: goalsData.protein || 150,
                    fat: goalsData.fat || 70,
                    carbohydrates: goalsData.carbohydrates || 250
                });
            }

            const mealsData = await api.getMeals(dateStr);

            // API возвращает объект с полями: {date, daily_goal, total_consumed, progress, meals}
            if (mealsData && mealsData.meals && Array.isArray(mealsData.meals)) {
                setMeals(mealsData.meals);

                // Используем total_consumed из ответа API (уже подсчитано на бэкенде)
                if (mealsData.total_consumed) {
                    setConsumed({
                        calories: Math.round(mealsData.total_consumed.calories || 0),
                        protein: Math.round(mealsData.total_consumed.protein || 0),
                        fat: Math.round(mealsData.total_consumed.fat || 0),
                        carbohydrates: Math.round(mealsData.total_consumed.carbohydrates || 0)
                    });
                }

                // Обновляем цели из ответа, если они там есть
                if (mealsData.daily_goal && !goals) {
                    setGoals({
                        calories: mealsData.daily_goal.calories || 2000,
                        protein: mealsData.daily_goal.protein || 150,
                        fat: mealsData.daily_goal.fat || 70,
                        carbohydrates: mealsData.daily_goal.carbohydrates || 250
                    });
                }
            } else if (Array.isArray(mealsData)) {
                // Fallback: если API вернул массив (старый формат)
                setMeals(mealsData);

                let totalCalories = 0;
                let totalProtein = 0;
                let totalFat = 0;
                let totalCarbs = 0;

                mealsData.forEach((meal: any) => {
                    meal.items?.forEach((item: any) => {
                        totalCalories += parseFloat(item.calories) || 0;
                        totalProtein += parseFloat(item.protein) || 0;
                        totalFat += parseFloat(item.fat) || 0;
                        totalCarbs += parseFloat(item.carbohydrates) || 0;
                    });
                });

                setConsumed({
                    calories: Math.round(totalCalories),
                    protein: Math.round(totalProtein),
                    fat: Math.round(totalFat),
                    carbohydrates: Math.round(totalCarbs)
                });
            }
        } catch (err) {
            console.error('Dashboard load error:', err);
            setError('Не удалось загрузить данные');
        } finally {
            setLoading(false);
        }
    };

    // F-033: Pull-to-refresh handler
    const handleRefresh = async () => {
        await loadDashboardData(selectedDate);
    };

    const handleDeleteMealClick = (e: React.MouseEvent, mealId: number) => {
        e.stopPropagation(); // Предотвратить переход к деталям
        setMealToDelete(mealId);
        setShowDeleteConfirm(true);
    };

    const handleConfirmDelete = async () => {
        if (!mealToDelete) return;

        try {
            setDeleting(true);
            await api.deleteMeal(mealToDelete);
            // Обновить данные после удаления
            await loadDashboardData(selectedDate);
            setShowDeleteConfirm(false);
            setMealToDelete(null);
        } catch (err) {
            console.error('Delete meal error:', err);
            const errorMessage = err instanceof Error ? err.message : 'Не удалось удалить приём пищи';
            setError(errorMessage);
            setShowDeleteConfirm(false);
            setMealToDelete(null);
        } finally {
            setDeleting(false);
        }
    };

    const getProgress = (consumed: number, goal: number) => {
        if (!goal) return 0;
        return Math.min((consumed / goal) * 100, 100);
    };

    const getProgressColor = (progress: number) => {
        if (progress < 50) return 'bg-blue-500';
        if (progress < 80) return 'bg-green-500';
        if (progress < 100) return 'bg-yellow-500';
        return 'bg-red-500';
    };

    const getRemainingCalories = () => {
        if (!goals) return 0;
        return Math.max(goals.calories - consumed.calories, 0);
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
    // Allow Browser Debug Mode to continue
    if (!webAppDetected && !isBrowserDebug && !webAppBrowserDebug) {
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

    // F-019: Show skeleton loader while loading dashboard data
    if (loading) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
                <SkeletonDashboard />
            </div>
        );
    }

    return (
        <PullToRefresh onRefresh={handleRefresh} disabled={loading}>
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-4 pb-24">
            <div className="max-w-lg mx-auto space-y-6">
                <Calendar selectedDate={selectedDate} onDateSelect={setSelectedDate} />

                <div className="text-center pt-4">
                    <h1 className="text-2xl font-bold text-gray-900">
                        Привет, {user?.first_name || 'друг'}!
                    </h1>
                    <p className="text-gray-500 mt-1">
                        {selectedDate.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}
                    </p>
                </div>

                {error && (
                    <div className="bg-red-50 border border-red-200 text-red-600 p-4 rounded-xl text-center">
                        {error}
                    </div>
                )}

                <div className="bg-gradient-to-br from-orange-500 to-red-500 rounded-3xl p-6 text-white shadow-xl">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-3">
                            <div className="bg-white/20 p-3 rounded-xl">
                                <Flame size={28} />
                            </div>
                            <div>
                                <p className="text-white/80 text-sm">Калории сегодня</p>
                                <p className="text-3xl font-bold">{consumed.calories}</p>
                            </div>
                        </div>
                        <div className="text-right">
                            <p className="text-white/80 text-sm">Цель</p>
                            <p className="text-xl font-semibold">{goals?.calories || '—'}</p>
                        </div>
                    </div>

                    <div className="bg-white/20 rounded-full h-3 mb-3">
                        <div
                            className="bg-white rounded-full h-3 transition-all duration-500"
                            style={{ width: `${getProgress(consumed.calories, goals?.calories || 1)}%` }}
                        />
                    </div>

                    <div className="flex justify-between text-sm">
                        <span className="text-white/80">Осталось: {getRemainingCalories()} ккал</span>
                        <span className="text-white/80">{Math.round(getProgress(consumed.calories, goals?.calories || 1))}%</span>
                    </div>
                </div>

                <div className="grid grid-cols-3 gap-3">
                    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
                        <div className="flex items-center gap-2 mb-2">
                            <Drumstick size={18} className="text-blue-500" />
                            <span className="text-xs text-gray-500">Белки</span>
                        </div>
                        <p className="text-xl font-bold text-gray-900">{consumed.protein}г</p>
                        <div className="bg-gray-100 rounded-full h-1.5 mt-2">
                            <div
                                className={`${getProgressColor(getProgress(consumed.protein, goals?.protein || 1))} rounded-full h-1.5 transition-all`}
                                style={{ width: `${getProgress(consumed.protein, goals?.protein || 1)}%` }}
                            />
                        </div>
                        <p className="text-xs text-gray-400 mt-1">из {goals?.protein || '—'}г</p>
                    </div>

                    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
                        <div className="flex items-center gap-2 mb-2">
                            <Droplets size={18} className="text-yellow-500" />
                            <span className="text-xs text-gray-500">Жиры</span>
                        </div>
                        <p className="text-xl font-bold text-gray-900">{consumed.fat}г</p>
                        <div className="bg-gray-100 rounded-full h-1.5 mt-2">
                            <div
                                className={`${getProgressColor(getProgress(consumed.fat, goals?.fat || 1))} rounded-full h-1.5 transition-all`}
                                style={{ width: `${getProgress(consumed.fat, goals?.fat || 1)}%` }}
                            />
                        </div>
                        <p className="text-xs text-gray-400 mt-1">из {goals?.fat || '—'}г</p>
                    </div>

                    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
                        <div className="flex items-center gap-2 mb-2">
                            <Wheat size={18} className="text-green-500" />
                            <span className="text-xs text-gray-500">Углеводы</span>
                        </div>
                        <p className="text-xl font-bold text-gray-900">{consumed.carbohydrates}г</p>
                        <div className="bg-gray-100 rounded-full h-1.5 mt-2">
                            <div
                                className={`${getProgressColor(getProgress(consumed.carbohydrates, goals?.carbohydrates || 1))} rounded-full h-1.5 transition-all`}
                                style={{ width: `${getProgress(consumed.carbohydrates, goals?.carbohydrates || 1)}%` }}
                            />
                        </div>
                        <p className="text-xs text-gray-400 mt-1">из {goals?.carbohydrates || '—'}г</p>
                    </div>
                </div>

                <button
                    onClick={() => navigate('/log', { state: { selectedDate: selectedDate.toISOString().split('T')[0] } })}
                    className="w-full bg-gradient-to-r from-blue-500 to-purple-500 text-white py-4 rounded-2xl font-bold flex items-center justify-center gap-3 shadow-lg active:scale-95 transition-transform"
                >
                    <Plus size={24} />
                    <span>Добавить прием пищи</span>
                </button>

                <div className="bg-white rounded-2xl p-5 shadow-sm border border-gray-100">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-bold text-gray-900">Сегодня</h2>
                        <span className="text-sm text-gray-500">{meals.length} приемов пищи</span>
                    </div>

                    {meals.length === 0 ? (
                        <div className="text-center py-8">
                            <p className="text-gray-400 mb-2">Пока нет записей</p>
                            <p className="text-sm text-gray-300">Добавьте первый прием пищи</p>
                        </div>
                    ) : (
                        <div className="space-y-3">
                            {meals.map((meal: any) => {
                                // Бэкенд возвращает поле 'items', а не 'food_items'
                                const items = meal.items || meal.food_items || [];
                                const mealCalories = items.reduce((sum: number, item: any) =>
                                    sum + (parseFloat(item.calories) || 0), 0) || 0;

                                return (
                                    <div
                                        key={meal.id}
                                        className="relative group"
                                    >
                                        <div
                                            onClick={() => navigate(`/meal/${meal.id}`, { state: { returnDate: selectedDate.toISOString().split('T')[0] } })}
                                            className="flex items-center justify-between p-3 bg-gray-50 rounded-xl cursor-pointer hover:bg-gray-100 transition-colors active:scale-[0.98]"
                                        >
                                            <div>
                                                <p className="font-medium text-gray-900">
                                                    {MEAL_TYPE_LABELS[meal.meal_type] || meal.meal_type}
                                                </p>
                                                <p className="text-sm text-gray-500">
                                                    {items.length} {items.length === 1 ? 'блюдо' : 'блюд'}
                                                </p>
                                            </div>
                                            <div className="flex items-center gap-3">
                                                <span className="font-bold text-orange-600">
                                                    {Math.round(mealCalories)} ккал
                                                </span>
                                                <button
                                                    onClick={(e) => handleDeleteMealClick(e, meal.id)}
                                                    className="p-2 bg-red-50 hover:bg-red-100 text-red-600 rounded-lg transition-colors opacity-0 group-hover:opacity-100"
                                                    aria-label="Удалить приём пищи"
                                                >
                                                    <Trash2 size={18} />
                                                </button>
                                                <ChevronRight size={18} className="text-gray-400" />
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {!goals && (
                    <div className="bg-yellow-50 border border-yellow-200 rounded-2xl p-4">
                        <p className="text-yellow-800 font-medium mb-2">Цели не установлены</p>
                        <p className="text-yellow-600 text-sm mb-3">
                            Установите дневные цели КБЖУ в профиле для отслеживания прогресса
                        </p>
                        <button
                            onClick={() => navigate('/profile')}
                            className="bg-yellow-500 text-white px-4 py-2 rounded-xl font-medium text-sm"
                        >
                            Установить цели
                        </button>
                    </div>
                )}
            </div>

            {/* Delete Confirmation Modal */}
            {showDeleteConfirm && (
                <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
                    <div className="bg-white rounded-3xl p-6 max-w-sm w-full shadow-2xl">
                        <div className="text-center mb-4">
                            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
                                <Trash2 className="text-red-600" size={32} />
                            </div>
                            <h3 className="text-xl font-bold text-gray-900 mb-2">
                                Удалить приём пищи?
                            </h3>
                            <p className="text-gray-600">
                                Это действие нельзя будет отменить. Все блюда в этом приёме пищи будут удалены.
                            </p>
                        </div>

                        <div className="space-y-3">
                            <button
                                onClick={handleConfirmDelete}
                                disabled={deleting}
                                className="w-full bg-red-600 hover:bg-red-700 text-white py-3 rounded-xl font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {deleting ? 'Удаление...' : 'Да, удалить'}
                            </button>
                            <button
                                onClick={() => {
                                    setShowDeleteConfirm(false);
                                    setMealToDelete(null);
                                }}
                                disabled={deleting}
                                className="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-3 rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                Отмена
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </div>
        </PullToRefresh>
    );
};

export default ClientDashboard;
