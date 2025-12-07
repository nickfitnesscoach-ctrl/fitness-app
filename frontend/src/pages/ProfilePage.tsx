import React, { useState, useEffect, useRef } from 'react';
import { User, Target, TrendingUp, Settings, Edit2, X, Camera, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useAppData } from '../contexts/AppDataContext';
import { api, UnauthorizedError, ForbiddenError } from '../services/api';
import { Profile } from '../types/profile';
import ProfileEditModal from '../components/ProfileEditModal';
import { calculateMifflinTargets, hasRequiredProfileData, getMissingProfileFields } from '../utils/mifflin';
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';
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
    const { user, logout, isBrowserDebug } = useAuth();
    // Use shared data from AppDataContext - loads instantly if already cached
    const { profile: contextProfile, goals: contextGoals, refreshProfile, refreshGoals, isLoading: contextLoading } = useAppData();
    const navigate = useNavigate();
    const { isReady, isTelegramWebApp: webAppDetected, isBrowserDebug: webAppBrowserDebug } = useTelegramWebApp();
    const [isEditing, setIsEditing] = useState(false);
    const [isEditingGoals, setIsEditingGoals] = useState(false);
    const [isWeeklyStatsOpen, setIsWeeklyStatsOpen] = useState(false);

    // Local goals state for editing (can differ from context until saved)
    const [goals, setGoals] = useState<UserGoals | null>(null);
    const [editedGoals, setEditedGoals] = useState<UserGoals | null>(null);
    const [error, setError] = useState<string | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);
    const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
    const [uploadingAvatar, setUploadingAvatar] = useState(false);

    // Local profile state (for editing/avatar)
    const [profile, setProfile] = useState<Profile | null>(null);

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

    // Initialize from context when available (instant, no API call)
    useEffect(() => {
        if (contextProfile) {
            setProfile(contextProfile);
            if (contextProfile.avatar_url) {
                setAvatarPreview(contextProfile.avatar_url);
            }
        }
    }, [contextProfile]);

    // Initialize goals from context
    useEffect(() => {
        if (contextGoals) {
            setGoals({
                ...contextGoals,
                avgCalories: 0,
                avgProtein: 0,
                avgFat: 0,
                avgCarbs: 0
            });
        }
    }, [contextGoals]);

    // Load weekly stats once on mount (separate from main data)
    useEffect(() => {
        loadWeeklyStats();
    }, []);

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

        setError(null);

        console.log('[ProfilePage] Saving goals:', editedGoals);

        try {
            const result = await api.updateGoals(editedGoals);
            console.log('[ProfilePage] Goals saved successfully:', result);

            setGoals(editedGoals);
            setIsEditingGoals(false);
            setEditedGoals(null);

            // Refresh context so other pages get updated goals
            await refreshGoals();
        } catch (err: any) {
            console.error('[ProfilePage] Failed to save goals:', err);
            const errorMsg = err.message || 'Ошибка при сохранении целей';
            setError(errorMsg);
        }
    };

    const handleAutoCalculate = () => {
        setError(null);

        // Check if profile has required data
        if (!hasRequiredProfileData(profile)) {
            const missingFields = getMissingProfileFields(profile);
            setError(
                `Для расчёта необходимо заполнить следующие поля в профиле: ${missingFields.join(', ')}. ` +
                'Пожалуйста, откройте редактирование профиля и заполните недостающие данные.'
            );
            return;
        }

        try {
            // Calculate targets using Mifflin-St Jeor formula on frontend
            const targets = calculateMifflinTargets(profile!);

            // Update the edited goals state with calculated values
            setEditedGoals({
                calories: targets.calories,
                protein: targets.protein,
                fat: targets.fat,
                carbohydrates: targets.carbohydrates,
            });
        } catch (err: any) {
            setError(err.message || 'Не удалось рассчитать цели. Проверьте данные профиля.');
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

    const handleProfileUpdate = (updatedProfile: Profile) => {
        setProfile(updatedProfile);
        // Refresh context so other pages get updated profile
        refreshProfile();
    };

    const handleLogout = () => {
        logout();
        window.location.href = '/';
    };

    const handleAvatarClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;

        console.log('[ProfilePage] Selected file:', {
            name: file.name,
            type: file.type,
            size: file.size,
            sizeKB: (file.size / 1024).toFixed(1)
        });

        // Limit size to 5MB
        if (file.size > 5 * 1024 * 1024) {
            const sizeMB = (file.size / (1024 * 1024)).toFixed(1);
            setError(`Размер файла ${sizeMB} МБ превышает лимит 5 МБ. Пожалуйста, выберите файл меньшего размера.`);
            return;
        }

        // iOS-specific: Check for HEIC format and inform user
        if (file.type === 'image/heic' || file.type === 'image/heif' || file.name.toLowerCase().endsWith('.heic') || file.name.toLowerCase().endsWith('.heif')) {
            console.log('[ProfilePage] HEIC/HEIF image detected, uploading directly (backend supports HEIC)');
        }

        // Show local preview immediately (works for most formats except HEIC)
        try {
            const objectUrl = URL.createObjectURL(file);
            setAvatarPreview(objectUrl);
        } catch (err) {
            console.warn('[ProfilePage] Failed to create preview:', err);
            // Continue with upload anyway
        }

        // Upload to backend
        setUploadingAvatar(true);
        setError(null);

        try {
            const updatedProfile = await api.uploadAvatar(file);
            setProfile(updatedProfile);
            // Update preview from server URL (with cache busting version parameter)
            setAvatarPreview(updatedProfile.avatar_url || null);
            console.log('[ProfilePage] Avatar uploaded successfully:', updatedProfile.avatar_url);
        } catch (err: any) {
            console.error('[ProfilePage] Failed to upload avatar:', err);

            // Parse error message
            let errorMessage = 'Не удалось загрузить фото. Попробуй ещё раз.';

            // Handle authentication errors specifically
            if (err instanceof UnauthorizedError || err instanceof ForbiddenError) {
                errorMessage = 'Сессия истекла. Пожалуйста, откройте приложение заново из Telegram.';
            } else if (err.message) {
                // Use backend error message if available
                errorMessage = err.message;

                // Add helpful context for common errors
                if (errorMessage.includes('формат') || errorMessage.includes('format')) {
                    errorMessage += ' На iOS фотографии могут быть в формате HEIC. Попробуйте сохранить фото как JPEG.';
                }
            }

            setError(errorMessage);

            // Revert to old avatar on any error
            setAvatarPreview(profile?.avatar_url || null);
        } finally {
            setUploadingAvatar(false);
            // Clear file input to allow re-selecting the same file
            if (event.target) {
                event.target.value = '';
            }
        }
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

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-4 pb-1">
            <div className="max-w-2xl mx-auto">


                {/* Profile Card */}
                <div className="bg-white rounded-3xl shadow-xl overflow-hidden mb-6">
                    <div className="h-32 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500"></div>

                    <div className="relative px-6 pb-6">
                        <div className="absolute -top-16 left-6">
                            <div
                                className="w-28 h-28 bg-white rounded-full p-2 shadow-xl cursor-pointer group relative"
                                onClick={handleAvatarClick}
                            >
                                <div className="w-full h-full rounded-full overflow-hidden relative">
                                    {avatarPreview ? (
                                        <img
                                            src={avatarPreview}
                                            alt="Avatar"
                                            className="w-full h-full object-cover"
                                        />
                                    ) : (
                                        <div className="w-full h-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center">
                                            <User size={48} className="text-white" />
                                        </div>
                                    )}

                                    {/* Upload Spinner */}
                                    {uploadingAvatar && (
                                        <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                                            <div className="animate-spin w-8 h-8 border-4 border-white border-t-transparent rounded-full"></div>
                                        </div>
                                    )}

                                    {/* Hover Overlay */}
                                    {!uploadingAvatar && (
                                        <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                            <Camera size={32} className="text-white drop-shadow-lg" />
                                        </div>
                                    )}
                                </div>
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    onChange={handleFileChange}
                                    accept="image/*"
                                    className="hidden"
                                    disabled={uploadingAvatar}
                                />
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

                    {contextLoading ? (
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
                <div className="bg-white rounded-3xl shadow-lg overflow-hidden mb-4 transition-all duration-300">
                    <div
                        className="py-0.5 px-4 flex items-center justify-between cursor-pointer active:bg-gray-50 transition-colors"
                        onClick={() => setIsWeeklyStatsOpen(!isWeeklyStatsOpen)}
                    >
                        <div className="flex items-center gap-3 flex-1 min-w-0">
                            <div className="w-12 h-12 bg-gradient-to-br from-purple-400 to-pink-500 rounded-xl flex items-center justify-center shrink-0 mt-1">
                                <TrendingUp size={24} className="text-white" />
                            </div>
                            <div className="min-w-0 flex flex-col justify-center">
                                <h2 className="text-lg font-bold text-gray-900 truncate leading-tight">Среднее КБЖУ за неделю</h2>
                                <p className="text-xs text-gray-500 leading-tight">Ваш прогресс</p>
                            </div>
                        </div>
                        <ChevronRight
                            size={24}
                            className={`text-gray-400 transition-transform duration-300 shrink-0 ${isWeeklyStatsOpen ? 'rotate-90' : ''}`}
                        />
                    </div>

                    <div className={`grid grid-cols-2 gap-2 px-4 pb-4 transition-all duration-300 origin-top ${isWeeklyStatsOpen ? 'opacity-100 max-h-[500px] mt-0' : 'opacity-0 max-h-0 overflow-hidden mt-0 pb-0'
                        }`}>
                        <div className="flex flex-col p-3 bg-orange-50 rounded-xl">
                            <span className="text-gray-600 text-xs mb-0.5">Калории</span>
                            <span className="text-xl font-bold text-orange-600">{goals?.avgCalories || 0}</span>
                            <span className="text-xs text-gray-500">ккал/день</span>
                        </div>
                        <div className="flex flex-col p-3 bg-blue-50 rounded-xl">
                            <span className="text-gray-600 text-xs mb-0.5">Белки</span>
                            <span className="text-xl font-bold text-blue-600">{goals?.avgProtein || 0}г</span>
                            <span className="text-xs text-gray-500">в среднем</span>
                        </div>
                        <div className="flex flex-col p-3 bg-yellow-50 rounded-xl">
                            <span className="text-gray-600 text-xs mb-0.5">Жиры</span>
                            <span className="text-xl font-bold text-yellow-600">{goals?.avgFat || 0}г</span>
                            <span className="text-xs text-gray-500">в среднем</span>
                        </div>
                        <div className="flex flex-col p-3 bg-green-50 rounded-xl">
                            <span className="text-gray-600 text-xs mb-0.5">Углеводы</span>
                            <span className="text-xl font-bold text-green-600">{goals?.avgCarbs || 0}г</span>
                            <span className="text-xs text-gray-500">в среднем</span>
                        </div>
                    </div>
                </div>

                {/* Settings */}
                <div
                    className="bg-white rounded-3xl shadow-lg py-3 px-4 cursor-pointer active:scale-[0.98] transition-all"
                    onClick={() => navigate('/settings')}
                >
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-12 h-12 bg-gradient-to-br from-gray-400 to-gray-600 rounded-xl flex items-center justify-center mt-1">
                                <Settings size={24} className="text-white" />
                            </div>
                            <div className="flex flex-col justify-center">
                                <h2 className="text-lg font-bold text-gray-900 leading-tight">Настройки</h2>
                                <p className="text-xs text-gray-500 leading-tight">Управление аккаунтом</p>
                            </div>
                        </div>
                        <ChevronRight size={24} className="text-gray-400" />
                    </div>
                </div>
            </div>

            <ProfileEditModal
                isOpen={isEditing}
                onClose={() => setIsEditing(false)}
                profile={profile}
                onProfileUpdated={handleProfileUpdate}
            />
        </div>
    );
};

export default ProfilePage;
