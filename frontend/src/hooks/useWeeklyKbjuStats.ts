import { useState, useEffect } from 'react';
import { api } from '../services/api';

interface DailyData {
    date: string;
    dayName: string;
    calories: number;
    protein: number;
    fat: number;
    carbs: number;
}

interface WeeklyStats {
    avgCalories: number;
    avgProtein: number;
    avgFat: number;
    avgCarbs: number;
    weeklyTotals: {
        calories: number;
        protein: number;
        fat: number;
        carbs: number;
    };
    dailyData: DailyData[];
    daysLogged: number;
    dateRange: string;
    loading: boolean;
}

export const useWeeklyKbjuStats = () => {
    const [stats, setStats] = useState<WeeklyStats>({
        avgCalories: 0,
        avgProtein: 0,
        avgFat: 0,
        avgCarbs: 0,
        weeklyTotals: { calories: 0, protein: 0, fat: 0, carbs: 0 },
        dailyData: [],
        daysLogged: 0,
        dateRange: '',
        loading: true
    });

    const getWeekDays = () => {
        const days = [];
        const today = new Date();
        const monday = new Date(today);
        const dayIdx = today.getDay(); // 0 is Sun, 1 is Mon
        const diff = today.getDate() - dayIdx + (dayIdx === 0 ? -6 : 1);
        monday.setDate(diff);
        monday.setHours(0, 0, 0, 0);

        for (let i = 0; i < 7; i++) {
            const date = new Date(monday);
            date.setDate(monday.getDate() + i);
            days.push(date);
        }
        return days;
    };

    const loadWeeklyStats = async () => {
        try {
            setStats(prev => ({ ...prev, loading: true }));
            const weekDaysData = getWeekDays();

            const dateRange = `${weekDaysData[0].toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })} — ${weekDaysData[6].toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}`;

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
            const dailyData: DailyData[] = [];

            mealsData.forEach((dayMeals, index) => {
                const date = weekDaysData[index];
                const dayName = date.toLocaleDateString('ru-RU', { weekday: 'short' });

                let dayCal = 0;
                let dayP = 0;
                let dayF = 0;
                let dayC = 0;

                if (dayMeals && dayMeals.length > 0) {
                    daysWithData++;
                    dayMeals.forEach((meal: any) => {
                        // Sum up macros from meal data
                        // Note: Backend might return pre-calculated calories in meal.calories 
                        // or we sum up food_items. In our refactored backend it is usually meal.calories
                        if (meal.calories) {
                            dayCal += meal.calories;
                            dayP += meal.protein || 0;
                            dayF += meal.fat || 0;
                            dayC += meal.carbohydrates || 0;
                        } else if (meal.food_items) {
                            meal.food_items.forEach((item: any) => {
                                dayCal += item.calories || 0;
                                dayP += item.protein || 0;
                                dayF += item.fat || 0;
                                dayC += item.carbohydrates || 0;
                            });
                        }
                    });
                }

                dailyData.push({
                    date: date.toISOString().split('T')[0],
                    dayName,
                    calories: Math.round(dayCal),
                    protein: Math.round(dayP),
                    fat: Math.round(dayF),
                    carbs: Math.round(dayC)
                });

                totalCalories += dayCal;
                totalProtein += dayP;
                totalFat += dayF;
                totalCarbs += dayC;
            });

            setStats({
                avgCalories: daysWithData > 0 ? Math.round(totalCalories / daysWithData) : 0,
                avgProtein: daysWithData > 0 ? Math.round(totalProtein / daysWithData) : 0,
                avgFat: daysWithData > 0 ? Math.round(totalFat / daysWithData) : 0,
                avgCarbs: daysWithData > 0 ? Math.round(totalCarbs / daysWithData) : 0,
                weeklyTotals: {
                    calories: Math.round(totalCalories),
                    protein: Math.round(totalProtein),
                    fat: Math.round(totalFat),
                    carbs: Math.round(totalCarbs)
                },
                dailyData,
                daysLogged: daysWithData,
                dateRange,
                loading: false
            });
        } catch (error) {
            console.error('Failed to load weekly stats:', error);
            setStats(prev => ({ ...prev, loading: false }));
        }
    };

    useEffect(() => {
        loadWeeklyStats();
    }, []);

    return stats;
};
