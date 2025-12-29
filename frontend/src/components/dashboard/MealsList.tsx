import React from 'react';
import { ChevronRight, Loader2 } from 'lucide-react';
import { Meal } from '../../types/meal';
import { MEAL_TYPE_LABELS } from '../../constants/meals';
import { MealPhotoStrip } from '../meal/MealPhotoGallery';

interface MealsListProps {
    meals: Meal[];
    onOpenMeal: (mealId: number) => void;
}

export const MealsList: React.FC<MealsListProps> = ({
    meals,
    onOpenMeal,
}) => {
    return (
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
                        // Backend returns 'items' field, with 'food_items' as fallback
                        const items = meal.items || meal.food_items || [];
                        const mealCalories = items.reduce((sum, item) =>
                            sum + (parseFloat(String(item.calories)) || 0), 0) || 0;

                        // Show spinner based on meal.status only (not individual photo statuses)
                        const isProcessing = meal.status === 'PROCESSING';

                        return (
                            <div
                                key={meal.id}
                                className="relative group"
                            >
                                <div
                                    onClick={() => onOpenMeal(meal.id)}
                                    className="flex items-center gap-3 p-3 bg-white border border-gray-100 rounded-2xl cursor-pointer hover:bg-gray-50 transition-colors active:scale-[0.98] shadow-sm"
                                >
                                    {/* 1. Photos (Fixed) */}
                                    <div className="w-16 min-w-16 flex items-center">
                                        <MealPhotoStrip
                                            photos={meal.photos || []}
                                            fallbackPhotoUrl={meal.photo_url}
                                        />
                                    </div>

                                    {/* 2. Text (Flexible) */}
                                    <div className="flex-1 min-w-0">
                                        <div className="font-semibold text-gray-900 flex items-center gap-2 truncate">
                                            {MEAL_TYPE_LABELS[meal.meal_type] || meal.meal_type}
                                            {isProcessing && (
                                                <Loader2 size={14} className="animate-spin text-blue-500 shrink-0" />
                                            )}
                                        </div>
                                        <div className="text-sm text-gray-500 truncate mt-0.5">
                                            {isProcessing ? 'Обработка...' : `${items.length} ${items.length === 1 ? 'блюдо' : 'блюд'}`}
                                        </div>
                                    </div>

                                    {/* 3. Kcal (Fixed) */}
                                    <div className="w-[84px] min-w-[84px] text-right whitespace-nowrap tabular-nums">
                                        <span className="font-bold text-orange-600">
                                            {Math.round(mealCalories)}
                                        </span>
                                        <span className="text-xs text-orange-400 font-medium ml-1">ккал</span>
                                    </div>

                                    {/* 4. Chevron (Fixed) */}
                                    <div className="w-6 min-w-6 flex justify-end">
                                        <ChevronRight size={18} className="text-gray-400" />
                                    </div>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
};
