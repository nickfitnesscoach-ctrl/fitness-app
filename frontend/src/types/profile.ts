/**
 * Profile types for FoodMind WebApp
 */

export interface Profile {
    id?: number;
    telegram_id?: number;
    username?: string;
    first_name?: string;
    last_name?: string;

    // Editable profile fields
    gender?: 'male' | 'female';
    birth_date?: string; // ISO date format YYYY-MM-DD
    height?: number; // cm
    weight?: number; // kg
    activity_level?: 'sedentary' | 'light' | 'moderate' | 'active' | 'very_active';
    goal?: 'weight_loss' | 'maintenance' | 'muscle_gain';
    timezone?: string; // e.g., "Europe/Moscow"

    // Metadata
    created_at?: string;
    updated_at?: string;
}
