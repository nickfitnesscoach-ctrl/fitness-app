export interface TotalConsumed {
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

export interface FoodItem {
    id: number;
    name: string;
    calories: number | string;
    protein: number | string;
    fat: number | string;
    carbohydrates: number | string;
}

export type MealPhotoStatus = 'PENDING' | 'PROCESSING' | 'SUCCESS' | 'FAILED' | 'CANCELLED';

export interface MealPhoto {
    id: number;
    image_url: string | null;
    status: MealPhotoStatus;
    status_display: string;
    error_message?: string | null;
    created_at: string;
}

export type MealStatus = 'DRAFT' | 'PROCESSING' | 'COMPLETE';

export interface Meal {
    id: number;
    meal_type: string;
    date: string;
    status?: MealStatus;
    status_display?: string;
    items: FoodItem[];
    food_items?: FoodItem[]; // Fallback for old format
    photos?: MealPhoto[]; // Multi-photo support
    photo_url?: string | null; // First photo URL (backward compatibility)
    photo_count?: number; // Number of successful photos
}
