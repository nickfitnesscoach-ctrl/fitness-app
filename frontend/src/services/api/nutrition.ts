/**
 * Nutrition API Module
 * 
 * Handles meals, food items, and daily goals.
 */

import {
    fetchWithTimeout,
    fetchWithRetry,
    getHeaders,
    log,
    resolveImageUrl
} from './client';
import { URLS } from './urls';
import type { Meal, FoodItem, CreateMealRequest, CreateFoodItemRequest, MealAnalysis } from './types';

// ============================================================
// Meals
// ============================================================

export const getMeals = async (date: string) => {
    try {
        const response = await fetchWithTimeout(`${URLS.meals}?date=${date}`, {
            headers: getHeaders(),
        });
        if (!response.ok) throw new Error('Failed to fetch meals');
        return await response.json();
    } catch (error) {
        console.error('Error fetching meals:', error);
        return [];
    }
};

export const createMeal = async (data: CreateMealRequest): Promise<Meal> => {
    log(`Creating meal: ${data.meal_type} for ${data.date}`);
    try {
        const response = await fetchWithRetry(URLS.meals, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMsg = errorData.detail || errorData.error || `Failed to create meal(${response.status})`;
            log(`Create meal error: ${errorMsg}`);
            throw new Error(errorMsg);
        }

        const meal = await response.json();
        log(`Meal created successfully: id=${meal.id}`);
        return meal;
    } catch (error) {
        console.error('Error creating meal:', error);
        throw error;
    }
};

export const deleteMeal = async (id: number): Promise<void> => {
    try {
        const response = await fetchWithTimeout(`${URLS.meals}${id}/`, {
            method: 'DELETE',
            headers: getHeaders(),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMessage = errorData.detail || errorData.error || `HTTP ${response.status}`;
            throw new Error(`Failed to delete meal: ${errorMessage}`);
        }
    } catch (error) {
        console.error('Error deleting meal:', error);
        throw error;
    }
};

/**
 * Get meal details for analysis view
 * 
 * Backend returns (MealSerializer):
 * {
 *   id: number,
 *   items: [{ id, name, grams, calories, protein, fat, carbohydrates }],
 *   photo_url: string | null,
 *   meal_type_display: string
 * }
 * @param signal - Optional AbortSignal for cancellation
 */
export const getMealAnalysis = async (
    id: number | string,
    signal?: AbortSignal
): Promise<MealAnalysis> => {
    try {
        const response = await fetchWithTimeout(
            `${URLS.meals}${id}/`,
            { headers: getHeaders() },
            undefined, // default timeout
            false,     // skipAuthCheck
            signal     // external abort signal
        );
        if (!response.ok) {
            throw new Error(`Failed to fetch meal analysis (${response.status})`);
        }

        const data = await response.json();
        const mainPhoto = data.photo_url || data.items?.find((item: FoodItem) => item.photo)?.photo || null;

        // Map backend fields directly - no transformation needed
        // Backend uses: id, name, grams, calories, protein, fat, carbohydrates
        return {
            id: data.id,
            photo_url: resolveImageUrl(mainPhoto),
            label: data.meal_type_display,
            recognized_items: (data.items || []).map((item: FoodItem) => ({
                id: item.id,
                name: item.name,
                grams: item.grams,
                calories: item.calories,
                protein: item.protein,
                fat: item.fat,
                carbohydrates: item.carbohydrates
            })),
            // Multi-photo support
            photos: (data.photos || []).map((photo: any) => ({
                id: photo.id,
                image_url: resolveImageUrl(photo.image_url),
                status: photo.status,
                status_display: photo.status_display,
                error_message: photo.error_message,
                created_at: photo.created_at
            })),
            photo_count: data.photo_count,
            status: data.status,
            status_display: data.status_display
        };
    } catch (error) {
        console.error('Error fetching meal analysis:', error);
        throw error;
    }
};

// ============================================================
// Food Items
// ============================================================

export const addFoodItem = async (mealId: number, data: CreateFoodItemRequest): Promise<FoodItem> => {
    log(`Adding food item "${data.name}" to meal ${mealId}`);
    try {
        const response = await fetchWithRetry(`${URLS.meals}${mealId}/items/`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMsg = errorData.detail || errorData.error || `Failed to add food item(${response.status})`;
            log(`Add food item error: ${errorMsg}`);
            throw new Error(errorMsg);
        }

        const foodItem = await response.json();
        log(`Food item added successfully: id=${foodItem.id}`);
        return foodItem;
    } catch (error) {
        console.error('Error adding food item:', error);
        throw error;
    }
};

export const deleteFoodItem = async (mealId: number, itemId: number): Promise<void> => {
    try {
        const response = await fetchWithTimeout(`${URLS.meals}${mealId}/items/${itemId}/`, {
            method: 'DELETE',
            headers: getHeaders(),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMessage = errorData.detail || errorData.error || `HTTP ${response.status}`;
            throw new Error(`Failed to delete food item: ${errorMessage}`);
        }
    } catch (error) {
        console.error('Error deleting food item:', error);
        throw error;
    }
};

export const updateFoodItem = async (
    mealId: number,
    itemId: number,
    // F-006 FIX: Backend expects 'grams', not 'amount_grams'
    data: { name?: string; grams?: number }
): Promise<FoodItem> => {
    try {
        const response = await fetchWithTimeout(`${URLS.meals}${mealId}/items/${itemId}/`, {
            method: 'PATCH',
            headers: {
                ...getHeaders(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMessage = errorData.detail || errorData.error || `HTTP ${response.status}`;
            throw new Error(`Failed to update food item: ${errorMessage}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Error updating food item:', error);
        throw error;
    }
};

// ============================================================
// Daily Goals
// ============================================================

export const getDailyGoals = async () => {
    try {
        const response = await fetchWithTimeout(URLS.goals, {
            headers: getHeaders(),
        });
        if (!response.ok) {
            if (response.status === 404) return null;
            throw new Error('Failed to fetch goals');
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching goals:', error);
        return null;
    }
};

export const updateGoals = async (data: {
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}) => {
    const requestData = {
        calories: data.calories,
        protein: data.protein,
        fat: data.fat,
        carbohydrates: data.carbohydrates,
        source: 'MANUAL',
        is_active: true,
    };

    log('[Goals] Updating goals with data: ' + JSON.stringify(requestData));

    try {
        const response = await fetchWithRetry(URLS.goals, {
            method: 'PUT',
            headers: getHeaders(),
            body: JSON.stringify(requestData),
        });

        log('[Goals] Response status: ' + response.status);

        if (!response.ok) {
            const errorText = await response.text();
            let errorData: Record<string, unknown> = {};
            try {
                errorData = JSON.parse(errorText);
            } catch {
                errorData = { raw: errorText };
            }

            log('[Goals] Update error: ' + JSON.stringify(errorData));

            if (response.status === 401) {
                throw new Error('401: Не авторизован. Откройте приложение через Telegram бота заново.');
            } else if (response.status === 403) {
                throw new Error('403: Доступ запрещён. Проверьте права доступа.');
            } else if (response.status === 400) {
                const detailMsg = errorData.detail || errorData.error || JSON.stringify(errorData);
                throw new Error('400: Некорректные данные - ' + detailMsg);
            } else if (response.status === 500) {
                throw new Error('500: Ошибка сервера. ' + (errorData.detail || errorData.error || ''));
            } else {
                throw new Error(`${response.status}: ${errorData.error || errorData.detail || 'Failed to update goals'}`);
            }
        }

        const result = await response.json();
        log('[Goals] Updated successfully: ' + JSON.stringify(result));
        return result;
    } catch (error) {
        console.error('[Goals] Error updating goals:', error);
        throw error;
    }
};

export const calculateGoals = async () => {
    try {
        const response = await fetchWithTimeout(URLS.calculateGoals, {
            method: 'POST',
            headers: getHeaders(),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to calculate goals');
        }
        return await response.json();
    } catch (error) {
        console.error('Error calculating goals:', error);
        throw error;
    }
};

export const setAutoGoals = async () => {
    try {
        const response = await fetchWithTimeout(URLS.setAutoGoals, {
            method: 'POST',
            headers: getHeaders(),
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to set auto goals');
        }
        return await response.json();
    } catch (error) {
        console.error('Error setting auto goals:', error);
        throw error;
    }
};

export const getWeeklyStats = async (startDate: string) => {
    try {
        const response = await fetchWithTimeout(`${URLS.weeklyStats}?start_date=${startDate}`, {
            headers: getHeaders(),
        });
        if (!response.ok) {
            throw new Error('Failed to fetch weekly stats');
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching weekly stats:', error);
        throw error;
    }
};
