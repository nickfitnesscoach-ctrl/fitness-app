import React, { useState, useEffect } from 'react';
import { User, Target, TrendingUp, Settings, LogOut, Edit2, X } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../services/api';

interface UserGoals {
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
    avgCalories?: number;
    avgProtein?: number;
    avgFat?: number;
    avgCarbs?: number;
}

const ProfilePage: React.FC = () => {
    const { user, logout } = useAuth();
    const [isEditing, setIsEditing] = useState(false);
    const [isEditingGoals, setIsEditingGoals] = useState(false);
    const [goals, setGoals] = useState<UserGoals | null>(null);
    const [editedGoals, setEditedGoals] = useState<UserGoals | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedDate, setSelectedDate] = useState(new Date());

    // Generate week days array
    const getWeekDays = () => {
        const days = [];
        const today = new Date();
        const currentDay = today.getDay();
        const monday = new Date(today);
        monday.setDate(today.getDate() - (currentDay === 0 ? 6 : currentDay - 1));

        for (let i = 0; i < 7; i++) {
            const date = new Date(monday);
            date.setDate(monday.getDate() + i);
            days.push(date);
        }
        return days;
    };

    const weekDays = getWeekDays();
    const dayNames = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];

    useEffect(() => {
        loadGoals();
        loadWeeklyStats();
    }, []);

    const loadGoals = async () => {
        try {
            const data = await api.getDailyGoals();
            if (data) {
                setGoals({
                    calories: data.calories || 2000,
                    protein: data.protein || 150,
                    fat: data.fat || 70,
                    carbohydrates: data.carbohydrates || 250
                });
            }
        } catch (error) {
            console.error('Failed to load goals:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleEditGoals = () => {
        setEditedGoals(goals || { calories: 2000, protein: 150, fat: 70, carbohydrates: 250 });
        setIsEditingGoals(true);
        setError(null);
    };

    // Auto-calculate calories from BJU: Protein*4 + Fat*9 + Carbs*4
    const calculateCaloriesFromBJU = (protein: number, fat: number, carbs: number) => {
        return Math.round(protein * 4 + fat * 9 + carbs * 4);
    };

    const handleBJUChange = (field: 'protein' | 'fat' | 'carbohydrates', value: number) => {
        if (!editedGoals) return;
        const newGoals = { ...editedGoals, [field]: value };
        newGoals.calories = calculateCaloriesFromBJU(newGoals.protein, newGoals.fat, newGoals.carbohydrates);
        setEditedGoals(newGoals);
    };

    const handleCancelEdit = () => {
        setEditedGoals(null);
        setIsEditingGoals(false);
        setError(null);
    };

    const handleSaveGoals = async () => {
        if (!editedGoals) return;

        setLoading(true);
        setError(null);

        try {
            // Just make the request - backend will handle auth
            await api.updateGoals(editedGoals);
            setGoals(editedGoals);
            setIsEditingGoals(false);
            setEditedGoals(null);
        } catch (err: any) {
            // Backend will return 401/403 if auth failed
            const errorMsg = err.message || 'Ошибка при сохранении целей';

            if (errorMsg.includes('401') || errorMsg.includes('403')) {
                setError('Ошибка авторизации. Закройте приложение и откройте заново через бота.');
            } else {
                setError(errorMsg);
            }
        } finally {
            setLoading(false);
        }
    };

    const handleAutoCalculate = async () => {
        setLoading(true);
        setError(null);
        try {
            const calculated = await api.setAutoGoals();
            setGoals(calculated);
            setEditedGoals(calculated);
        } catch (err: any) {
            setError(err.message || 'Не удалось рассчитать цели. Убедитесь, что заполнен профиль.');
        } finally {
            setLoading(false);
        }
    };

    const loadWeeklyStats = async () => {
        try {
            const weekDaysData = getWeekDays();
            const mealsData = await Promise.all(
                weekDaysData.map(date => {
                    const dateStr = date.toISOString().split('T')[0];
                    return api.getMeals(dateStr).catch(() => []);
                })
            );

            let totalCalories = 0;
            let totalProtein = 0;
            let totalFat = 0;
            let totalCarbs = 0;
            let daysWithData = 0;

            mealsData.forEach(dayMeals => {
                if (dayMeals && dayMeals.length > 0) {
                    daysWithData++;
                    dayMeals.forEach((meal: any) => {
                        meal.food_items?.forEach((item: any) => {
                            totalCalories += item.calories || 0;
                            totalProtein += item.protein || 0;
                            totalFat += item.fat || 0;
                            totalCarbs += item.carbohydrates || 0;
                        });
                    });
                }
            });

            const avgCalories = daysWithData > 0 ? Math.round(totalCalories / daysWithData) : 0;
            const avgProtein = daysWithData > 0 ? Math.round(totalProtein / daysWithData) : 0;
            const avgFat = daysWithData > 0 ? Math.round(totalFat / daysWithData) : 0;
            const avgCarbs = daysWithData > 0 ? Math.round(totalCarbs / daysWithData) : 0;

            setGoals(prev => ({
                ...prev!,
                avgCalories,
                avgProtein,
                avgFat,
                avgCarbs
            }));
        } catch (error) {
            console.error('Failed to load weekly stats:', error);
        }
    };

    const handleLogout = () => {
        logout();
        window.location.href = '/';
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-4 pb-24">
            <div className="max-w-2xl mx-auto">
                {/* Week Calendar */}
                <div className="bg-white rounded-3xl shadow-lg p-4 mb-6">
                    <div className="grid grid-cols-7 gap-2">
                        {weekDays.map((date, index) => {
                            const isToday = date.toDateString() === new Date().toDateString();
                            const isSelected = date.toDateString() === selectedDate.toDateString();

                            return (
                                <button
                                    key={index}
                                    onClick={() => setSelectedDate(date)}
                                    className={`flex flex-col items-center p-3 rounded-2xl transition-all ${isSelected
                                        ? 'bg-gradient-to-br from-blue-500 to-purple-500 text-white shadow-lg scale-105'
                                        : isToday
                                            ? 'bg-blue-50 text-blue-600'
                                            : 'hover:bg-gray-50 text-gray-600'
                                        }`}
                                >
                                    <span className={`text-xs font-medium mb-1 ${isSelected ? 'text-white' : 'text-gray-500'}`}>
                                        {dayNames[index]}
                                    </span>
                                    <span className={`text-lg font-bold ${isSelected ? 'text-white' : ''}`}>
                                        {date.getDate()}
                                    </span>
                                </button>
                            );
                        })}
                    </div>
                </div>

                {/* Profile Card */}
                <div className="bg-white rounded-3xl shadow-xl overflow-hidden mb-6">
                    <div className="h-32 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500"></div>

                    <div className="relative px-6 pb-6">
                        <div className="absolute -top-16 left-6">
                            <div className="w-28 h-28 bg-white rounded-full p-2 shadow-xl">
                                <div className="w-full h-full bg-gradient-to-br from-blue-400 to-purple-500 rounded-full flex items-center justify-center">
                                    <User size={48} className="text-white" />
                                </div>
                            </div>
                        </div>

                        <div className="flex justify-end pt-4">
                            <button
                                onClick={() => setIsEditing(!isEditing)}
                                className="flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-600 rounded-xl hover:bg-blue-100 transition-colors"
                            >
                                {isEditing ? (
                                    <>
                                        <X size={18} />
                                        <span className="text-sm font-medium">Отменить</span>
                                    </>
                                ) : (
                                    <>
                                        <Edit2 size={18} />
                                        <span className="text-sm font-medium">Редактировать</span>
                                    </>
                                )}
                            </button>
                        </div>

                        <div className="mt-4">
                            <h1 className="text-2xl font-bold text-gray-900">
                                {user?.first_name} {user?.last_name || ''}
                            </h1>
                            <p className="text-gray-500 mt-1">@{user?.username || 'user'}</p>
                            <p className="text-sm text-gray-400 mt-2">Telegram ID: {user?.telegram_id}</p>
                        </div>
                    </div>
                </div>

                {/* Goals Section */}
                <div className="bg-white rounded-3xl shadow-lg p-6 mb-6">
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-3">
                            <div className="w-12 h-12 bg-gradient-to-br from-green-400 to-emerald-500 rounded-xl flex items-center justify-center">
                                <Target size={24} className="text-white" />
                            </div>
                            <div>
                                <h2 className="text-xl font-bold text-gray-900">Мои цели</h2>
                                <p className="text-sm text-gray-500">Дневные показатели КБЖУ</p>
                            </div>
                        </div>
                        {!isEditingGoals && (
                            <button
                                onClick={handleEditGoals}
                                className="px-4 py-2 bg-blue-50 text-blue-600 rounded-xl hover:bg-blue-100 transition-colors text-sm font-medium"
                            >
                                Редактировать
                            </button>
                        )}
                    </div>

                    {error && (
                        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
                            {error}
                        </div>
                    )}

                    {loading ? (
                        <div className="flex justify-center py-8">
                            <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full"></div>
                        </div>
                    ) : isEditingGoals && editedGoals ? (
                        <div>
                            {/* Calories - auto-calculated, shown prominently */}
                            <div className="bg-gradient-to-br from-orange-500 to-red-500 p-5 rounded-2xl mb-4 text-white">
                                <div className="text-sm text-white/80 mb-1">Калории (рассчитано автоматически)</div>
                                <div className="text-4xl font-bold">{editedGoals.calories} ккал</div>
                                <div className="text-xs text-white/60 mt-1">= Б×4 + Ж×9 + У×4</div>
                            </div>

                            <div className="grid grid-cols-3 gap-3 mb-4">
                                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-4 rounded-2xl border-2 border-blue-100">
                                    <label className="text-sm text-blue-600 font-medium mb-2 block">Белки</label>
                                    <input
                                        type="number"
                                        value={editedGoals.protein}
                                        onChange={(e) => handleBJUChange('protein', parseInt(e.target.value) || 0)}
                                        className="w-full text-2xl font-bold text-blue-700 bg-white/50 rounded-lg px-2 py-1 border-2 border-blue-200 focus:outline-none focus:border-blue-400"
                                    />
                                    <div className="text-xs text-blue-500 mt-1">г/день</div>
                                </div>
                                <div className="bg-gradient-to-br from-yellow-50 to-amber-50 p-4 rounded-2xl border-2 border-yellow-100">
                                    <label className="text-sm text-yellow-600 font-medium mb-2 block">Жиры</label>
                                    <input
                                        type="number"
                                        value={editedGoals.fat}
                                        onChange={(e) => handleBJUChange('fat', parseInt(e.target.value) || 0)}
                                        className="w-full text-2xl font-bold text-yellow-700 bg-white/50 rounded-lg px-2 py-1 border-2 border-yellow-200 focus:outline-none focus:border-yellow-400"
                                    />
                                    <div className="text-xs text-yellow-500 mt-1">г/день</div>
                                </div>
                                <div className="bg-gradient-to-br from-green-50 to-emerald-50 p-4 rounded-2xl border-2 border-green-100">
                                    <label className="text-sm text-green-600 font-medium mb-2 block">Углеводы</label>
                                    <input
                                        type="number"
                                        value={editedGoals.carbohydrates}
                                        onChange={(e) => handleBJUChange('carbohydrates', parseInt(e.target.value) || 0)}
                                        className="w-full text-2xl font-bold text-green-700 bg-white/50 rounded-lg px-2 py-1 border-2 border-green-200 focus:outline-none focus:border-green-400"
                                    />
                                    <div className="text-xs text-green-500 mt-1">г/день</div>
                                </div>
                            </div>
                            <div className="flex gap-3">
                                <button
                                    onClick={handleAutoCalculate}
                                    className="flex-1 px-4 py-3 bg-purple-50 text-purple-600 rounded-xl hover:bg-purple-100 transition-colors font-medium"
                                >
                                    Рассчитать по формуле Маффина-Сан Жеора
                                </button>
                            </div>
                            <div className="flex gap-3 mt-3">
                                <button
                                    onClick={handleSaveGoals}
                                    className="flex-1 px-4 py-3 bg-green-500 text-white rounded-xl hover:bg-green-600 transition-colors font-medium"
                                >
                                    Сохранить
                                </button>
                                <button
                                    onClick={handleCancelEdit}
                                    className="flex-1 px-4 py-3 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors font-medium"
                                >
                                    Отменить
                                </button>
                            </div>
                        </div>
                    ) : goals ? (
                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-gradient-to-br from-orange-50 to-red-50 p-4 rounded-2xl border-2 border-orange-100">
                                <div className="text-sm text-orange-600 font-medium mb-1">Калории</div>
                                <div className="text-2xl font-bold text-orange-700">{goals.calories}</div>
                                <div className="text-xs text-orange-500 mt-1">ккал/день</div>
                            </div>
                            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-4 rounded-2xl border-2 border-blue-100">
                                <div className="text-sm text-blue-600 font-medium mb-1">Белки</div>
                                <div className="text-2xl font-bold text-blue-700">{goals.protein}</div>
                                <div className="text-xs text-blue-500 mt-1">г/день</div>
                            </div>
                            <div className="bg-gradient-to-br from-yellow-50 to-amber-50 p-4 rounded-2xl border-2 border-yellow-100">
                                <div className="text-sm text-yellow-600 font-medium mb-1">Жиры</div>
                                <div className="text-2xl font-bold text-yellow-700">{goals.fat}</div>
                                <div className="text-xs text-yellow-500 mt-1">г/день</div>
                            </div>
                            <div className="bg-gradient-to-br from-green-50 to-emerald-50 p-4 rounded-2xl border-2 border-green-100">
                                <div className="text-sm text-green-600 font-medium mb-1">Углеводы</div>
                                <div className="text-2xl font-bold text-green-700">{goals.carbohydrates}</div>
                                <div className="text-xs text-green-500 mt-1">г/день</div>
                            </div>
                        </div>
                    ) : (
                        <div className="text-center py-8">
                            <p className="text-gray-500 mb-4">Цели не установлены</p>
                            <button
                                onClick={handleEditGoals}
                                className="px-6 py-2 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-medium"
                            >
                                Установить цели
                            </button>
                        </div>
                    )}
                </div>

                {/* Statistics - Average Weekly KBJU */}
                <div className="bg-white rounded-3xl shadow-lg p-6 mb-6">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="w-12 h-12 bg-gradient-to-br from-purple-400 to-pink-500 rounded-xl flex items-center justify-center">
                            <TrendingUp size={24} className="text-white" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-gray-900">Среднее КБЖУ за неделю</h2>
                            <p className="text-sm text-gray-500">Ваш прогресс</p>
                        </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                        <div className="flex flex-col p-4 bg-orange-50 rounded-xl">
                            <span className="text-gray-600 text-sm mb-1">Калории</span>
                            <span className="text-2xl font-bold text-orange-600">{goals?.avgCalories || 0}</span>
                            <span className="text-xs text-gray-500">ккал/день</span>
                        </div>
                        <div className="flex flex-col p-4 bg-blue-50 rounded-xl">
                            <span className="text-gray-600 text-sm mb-1">Белки</span>
                            <span className="text-2xl font-bold text-blue-600">{goals?.avgProtein || 0}г</span>
                            <span className="text-xs text-gray-500">в среднем</span>
                        </div>
                        <div className="flex flex-col p-4 bg-yellow-50 rounded-xl">
                            <span className="text-gray-600 text-sm mb-1">Жиры</span>
                            <span className="text-2xl font-bold text-yellow-600">{goals?.avgFat || 0}г</span>
                            <span className="text-xs text-gray-500">в среднем</span>
                        </div>
                        <div className="flex flex-col p-4 bg-green-50 rounded-xl">
                            <span className="text-gray-600 text-sm mb-1">Углеводы</span>
                            <span className="text-2xl font-bold text-green-600">{goals?.avgCarbs || 0}г</span>
                            <span className="text-xs text-gray-500">в среднем</span>
                        </div>
                    </div>
                </div>

                {/* Settings */}
                <div className="bg-white rounded-3xl shadow-lg p-6 mb-6">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="w-12 h-12 bg-gradient-to-br from-gray-400 to-gray-600 rounded-xl flex items-center justify-center">
                            <Settings size={24} className="text-white" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-gray-900">Настройки</h2>
                            <p className="text-sm text-gray-500">Управление аккаунтом</p>
                        </div>
                    </div>
                    <div className="space-y-3">
                        <button className="w-full flex items-center justify-between p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
                            <span className="text-gray-700 font-medium">Уведомления</span>
                            <span className="text-sm text-gray-500">Вкл</span>
                        </button>
                        <button className="w-full flex items-center justify-between p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
                            <span className="text-gray-700 font-medium">Язык</span>
                            <span className="text-sm text-gray-500">Русский</span>
                        </button>
                        <button className="w-full flex items-center justify-between p-4 bg-gray-50 rounded-xl hover:bg-gray-100 transition-colors">
                            <span className="text-gray-700 font-medium">Часовой пояс</span>
                            <span className="text-sm text-gray-500">GMT+3</span>
                        </button>
                    </div>
                </div>

                {/* Logout Button */}
                <button
                    onClick={handleLogout}
                    className="w-full flex items-center justify-center gap-3 p-4 bg-red-50 text-red-600 rounded-2xl hover:bg-red-100 transition-colors font-medium shadow-sm"
                >
                    <LogOut size={20} />
                    <span>Выйти из аккаунта</span>
                </button>
            </div>
        </div>
    );
};

export default ProfilePage;
