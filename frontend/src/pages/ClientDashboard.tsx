import React, { useEffect, useState } from 'react';
import { Flame, Drumstick, Droplets, Wheat, Plus, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';

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
    const { user } = useAuth();
    const { isReady, isTelegramWebApp } = useTelegramWebApp();

    const [loading, setLoading] = useState(true);
    const [goals, setGoals] = useState<DailyGoal | null>(null);
    const [consumed, setConsumed] = useState<TotalConsumed>({ calories: 0, protein: 0, fat: 0, carbohydrates: 0 });
    const [meals, setMeals] = useState<Meal[]>([]);
    const [error, setError] = useState<string | null>(null);

    const today = new Date().toISOString().split('T')[0];

    useEffect(() => {
        // Wait for WebApp to be ready before loading data
        if (isReady && isTelegramWebApp) {
            loadDashboardData();
        }
    }, [isReady, isTelegramWebApp]);

    const loadDashboardData = async () => {
        setLoading(true);
        setError(null);

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

            const mealsData = await api.getMeals(today);
            if (Array.isArray(mealsData)) {
                setMeals(mealsData);

                let totalCalories = 0;
                let totalProtein = 0;
                let totalFat = 0;
                let totalCarbs = 0;

                mealsData.forEach((meal: any) => {
                    meal.food_items?.forEach((item: any) => {
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
    if (!isTelegramWebApp) {
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

    // Loading dashboard data
    if (loading) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-4 pb-24">
            <div className="max-w-lg mx-auto space-y-6">
                <div className="text-center pt-4">
                    <h1 className="text-2xl font-bold text-gray-900">
                        Привет, {user?.first_name || 'друг'}!
                    </h1>
                    <p className="text-gray-500 mt-1">
                        {new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}
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
                    onClick={() => navigate('/client/log')}
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
                            {meals.map((meal) => {
                                const mealCalories = meal.food_items?.reduce((sum: number, item: any) =>
                                    sum + (parseFloat(item.calories) || 0), 0) || 0;

                                return (
                                    <div
                                        key={meal.id}
                                        className="flex items-center justify-between p-3 bg-gray-50 rounded-xl"
                                    >
                                        <div>
                                            <p className="font-medium text-gray-900">
                                                {MEAL_TYPE_LABELS[meal.meal_type] || meal.meal_type}
                                            </p>
                                            <p className="text-sm text-gray-500">
                                                {meal.food_items?.length || 0} блюд
                                            </p>
                                        </div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-bold text-orange-600">
                                                {Math.round(mealCalories)} ккал
                                            </span>
                                            <ChevronRight size={18} className="text-gray-400" />
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
                            onClick={() => navigate('/client/profile')}
                            className="bg-yellow-500 text-white px-4 py-2 rounded-xl font-medium text-sm"
                        >
                            Установить цели
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
};

export default ClientDashboard;
