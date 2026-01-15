import React, { useEffect, useRef } from 'react';
import { Drumstick, Droplets, Wheat, Plus } from 'lucide-react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useAppData } from '../contexts/AppDataContext';
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';
import { useDailyMeals } from '../hooks/useDailyMeals';

import Calendar from '../components/Calendar';
import PullToRefresh from '../components/PullToRefresh';
import { SkeletonMealsList } from '../components/Skeleton';
import { DailyCaloriesCard } from '../components/dashboard/DailyCaloriesCard';
import { MacrosGrid, MacroInfo } from '../components/dashboard/MacrosGrid';
import { MealsList } from '../components/dashboard/MealsList';
import { PageContainer } from '../components/shared/PageContainer';

import { getProgress, getProgressColor } from '../utils/progress';

const ClientDashboard: React.FC = () => {
    const navigate = useNavigate();
    const { user, isBrowserDebug } = useAuth();
    const { goals } = useAppData();
    const { isReady, isTelegramWebApp: webAppDetected, isBrowserDebug: webAppBrowserDebug } = useTelegramWebApp();
    const [searchParams, setSearchParams] = useSearchParams();

    // Get date from URL params or use today
    const getInitialDate = () => {
        const dateParam = searchParams.get('date');
        if (dateParam) {
            return new Date(dateParam);
        }
        return new Date();
    };

    // Daily meals hook manages all meal data and loading state
    const isWebAppEnabled = isReady && (webAppDetected || isBrowserDebug || webAppBrowserDebug);
    const dailyMeals = useDailyMeals({
        initialDate: getInitialDate(),
        enabled: isWebAppEnabled
    });

    // Update URL when date changes
    useEffect(() => {
        const dateStr = dailyMeals.selectedDate.toISOString().split('T')[0];
        const newParams = new URLSearchParams(searchParams);
        newParams.set('date', dateStr);
        setSearchParams(newParams, { replace: true });
    }, [dailyMeals.selectedDate, searchParams, setSearchParams]);

    // Handle refresh=1 param (from FoodLogPage after "Готово")
    useEffect(() => {
        const shouldRefresh = searchParams.get('refresh') === '1';
        if (shouldRefresh && isWebAppEnabled) {
            // Clear refresh param and trigger refresh
            const newParams = new URLSearchParams(searchParams);
            newParams.delete('refresh');
            setSearchParams(newParams, { replace: true });

            // Initial refresh with small delay to let backend finalize
            setTimeout(() => {
                dailyMeals.refresh();
            }, 300);
        }
    }, [searchParams, isWebAppEnabled, setSearchParams, dailyMeals]);

    // P0: Listen for AI photo events and refresh immediately
    // P0-3: Anti-duplicate protection (prevents double refresh in StrictMode)
    const lastProcessedEventRef = useRef<{ taskId: string; timestamp: number } | null>(null);

    useEffect(() => {
        if (!isWebAppEnabled) return;

        const handleAiPhotoEvent = (eventName: string) => (event: Event) => {
            const customEvent = event as CustomEvent<{ taskId: string; mealId?: number; error?: string }>;
            const { taskId, mealId, error } = customEvent.detail || {};

            console.log(`[Dashboard] ${eventName} event:`, { taskId, mealId, error });

            // P0-3: Deduplicate events (ignore same taskId within 2 seconds)
            const now = Date.now();
            const lastEvent = lastProcessedEventRef.current;

            if (lastEvent && lastEvent.taskId === taskId && now - lastEvent.timestamp < 2000) {
                console.log('[Dashboard] Ignoring duplicate event for taskId:', taskId);
                return;
            }

            // Update ref and trigger refresh
            lastProcessedEventRef.current = { taskId, timestamp: now };
            console.log('[Dashboard] Triggering refresh for taskId:', taskId);
            dailyMeals.refresh();
        };

        const handleSuccess = handleAiPhotoEvent('ai:photo-success');
        const handleFailed = handleAiPhotoEvent('ai:photo-failed');

        window.addEventListener('ai:photo-success', handleSuccess);
        window.addEventListener('ai:photo-failed', handleFailed);

        return () => {
            window.removeEventListener('ai:photo-success', handleSuccess);
            window.removeEventListener('ai:photo-failed', handleFailed);
        };
    }, [isWebAppEnabled, dailyMeals]);

    // Poll for meals with PROCESSING status
    useEffect(() => {
        if (!isWebAppEnabled) return;

        const hasProcessing = dailyMeals.meals.some(meal => meal.status === 'PROCESSING');
        if (!hasProcessing) return;

        // Poll every 2 seconds while there are processing meals
        const pollInterval = setInterval(() => {
            dailyMeals.refresh();
        }, 2000);

        return () => clearInterval(pollInterval);
    }, [dailyMeals.meals, isWebAppEnabled, dailyMeals]);

    // Pull-to-refresh handler
    const handleRefresh = async () => {
        await dailyMeals.refresh();
    };

    const getRemainingCalories = () => {
        if (!goals) return 0;
        return Math.max(goals.calories - dailyMeals.consumed.calories, 0);
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

    // Prepare macros data
    const macrosData: MacroInfo[] = [
        {
            label: 'Белки',
            icon: <Drumstick size={18} className="text-blue-500" />,
            consumed: dailyMeals.consumed.protein,
            goal: goals?.protein,
            progressPercent: getProgress(dailyMeals.consumed.protein, goals?.protein || 1),
            barColorClass: getProgressColor(getProgress(dailyMeals.consumed.protein, goals?.protein || 1))
        },
        {
            label: 'Жиры',
            icon: <Droplets size={18} className="text-yellow-500" />,
            consumed: dailyMeals.consumed.fat,
            goal: goals?.fat,
            progressPercent: getProgress(dailyMeals.consumed.fat, goals?.fat || 1),
            barColorClass: getProgressColor(getProgress(dailyMeals.consumed.fat, goals?.fat || 1))
        },
        {
            label: 'Углеводы',
            icon: <Wheat size={18} className="text-green-500" />,
            consumed: dailyMeals.consumed.carbohydrates,
            goal: goals?.carbohydrates,
            progressPercent: getProgress(dailyMeals.consumed.carbohydrates, goals?.carbohydrates || 1),
            barColorClass: getProgressColor(getProgress(dailyMeals.consumed.carbohydrates, goals?.carbohydrates || 1))
        }
    ];

    return (
        <PullToRefresh onRefresh={handleRefresh} disabled={dailyMeals.loading}>
            <div className="flex-1 bg-gradient-to-br from-blue-50 via-white to-purple-50">
                <PageContainer className="py-6 space-y-[var(--section-gap)]">
                    <Calendar selectedDate={dailyMeals.selectedDate} onDateSelect={dailyMeals.setSelectedDate} />

                    <div className="text-center pt-2">
                        <h1 className="text-2xl font-bold text-gray-900">
                            Привет, {user?.first_name || 'друг'}!
                        </h1>
                        <p className="text-gray-500 mt-1">
                            {dailyMeals.selectedDate.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' })}
                        </p>
                    </div>

                    {dailyMeals.error && (
                        <div className="bg-red-50 border border-red-200 text-red-600 p-4 rounded-[var(--radius-card)] text-center">
                            {dailyMeals.error}
                        </div>
                    )}

                    <DailyCaloriesCard
                        consumedCalories={dailyMeals.consumed.calories}
                        goalCalories={goals?.calories}
                        remainingCalories={getRemainingCalories()}
                        progressPercent={getProgress(dailyMeals.consumed.calories, goals?.calories || 1)}
                    />

                    <MacrosGrid items={macrosData} />

                    <button
                        onClick={() => navigate('/log', { state: { selectedDate: dailyMeals.selectedDate.toISOString().split('T')[0] } })}
                        className="w-full bg-gradient-to-r from-blue-500 to-purple-500 text-white py-4 rounded-[var(--radius-card)] font-bold flex items-center justify-center gap-3 shadow-lg active:scale-95 transition-transform"
                    >
                        <Plus size={24} />
                        <span>Добавить прием пищи</span>
                    </button>

                    {/* Meals list with skeleton only in this area */}
                    {dailyMeals.loading && dailyMeals.meals.length === 0 ? (
                        <SkeletonMealsList />
                    ) : (
                        <MealsList
                            meals={dailyMeals.meals}
                            onOpenMeal={(mealId) => navigate(`/meal/${mealId}`, {
                                state: { returnDate: dailyMeals.selectedDate.toISOString().split('T')[0] }
                            })}
                        />
                    )}

                    {!goals && (
                        <div className="bg-yellow-50 border border-yellow-200 rounded-[var(--radius-card)] p-[var(--card-p)]">
                            <p className="text-yellow-800 font-medium mb-2">Цели не установлены</p>
                            <p className="text-yellow-600 text-sm mb-3">
                                Установите дневные цели КБЖУ в профиле для отслеживания прогресса
                            </p>
                            <button
                                onClick={() => navigate('/profile')}
                                className="bg-yellow-500 text-white px-4 py-2 rounded-xl font-medium text-sm transition-colors active:scale-95"
                            >
                                Установить цели
                            </button>
                        </div>
                    )}
                </PageContainer>
            </div>
        </PullToRefresh>
    );
};

export default ClientDashboard;
