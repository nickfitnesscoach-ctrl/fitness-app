/**
 * API Types
 * 
 * Shared types for API requests and responses.
 */

// ============================================================
// Nutrition Types
// ============================================================

export interface Meal {
    id: number;
    meal_type: 'BREAKFAST' | 'LUNCH' | 'DINNER' | 'SNACK';
    meal_type_display?: string;
    date: string;
    created_at: string;
    items?: FoodItem[];
    total?: {
        calories: number;
        protein: number;
        fat: number;
        carbohydrates: number;
    };
}

export interface FoodItem {
    id: number;
    name: string;
    photo?: string;
    grams: number;
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
    created_at?: string;
    updated_at?: string;
}

export interface CreateMealRequest {
    date: string;
    meal_type: 'BREAKFAST' | 'LUNCH' | 'DINNER' | 'SNACK';
}

export interface CreateFoodItemRequest {
    name: string;
    grams: number;
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
    photo?: File;
}

// ============================================================
// Meal Analysis Types
// ============================================================

/**
 * Item from GET /meals/{id}/ response (backend MealSerializer)
 * Backend field names: id, name, grams, calories, protein, fat, carbohydrates
 */
export interface RecognizedItemAnalysis {
    id: number;
    name: string;
    grams: number;
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

export type MealPhotoStatus = 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'FAILED' | 'CANCELLED';

export interface MealPhoto {
    id: number;
    image_url: string | null;
    status: MealPhotoStatus;
    status_display?: string;
    error_message?: string | null;
    created_at?: string;
}

export type MealStatus = 'DRAFT' | 'PROCESSING' | 'COMPLETE';

export interface MealAnalysis {
    id: number;
    photo_url: string | null;
    label: string;
    recognized_items: RecognizedItemAnalysis[];
    // Multi-photo support
    photos?: MealPhoto[];
    photo_count?: number;
    status?: MealStatus;
    status_display?: string;
}

// ============================================================
// Auth Types
// ============================================================

export interface TrainerPanelAuthResponse {
    ok: boolean;
    user_id: number;
    role: 'admin';
}

export interface AuthResponse {
    user: {
        id: number;
        username: string;
        telegram_id: number;
        first_name: string;
        last_name?: string;
        completed_ai_test: boolean;
        is_client?: boolean;
    };
    is_admin?: boolean;
}
