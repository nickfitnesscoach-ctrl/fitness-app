/**
 * Profile types for FoodMind WebApp
 */

export interface Profile {
    id?: number;
    telegram_id?: number;
    username?: string;
    first_name?: string;
    last_name?: string;

    // Editable profile fields (Backend format)
    gender?: 'M' | 'F'; // Backend uses M/F not male/female
    birth_date?: string; // ISO date format YYYY-MM-DD
    height?: number; // cm
    weight?: number; // kg
    activity_level?: 'sedentary' | 'lightly_active' | 'moderately_active' | 'very_active' | 'extra_active'; // Backend format
    goal_type?: 'weight_loss' | 'maintenance' | 'weight_gain'; // Backend uses goal_type not goal
    timezone?: string; // e.g., "Europe/Moscow"
    avatar_url?: string | null; // URL to user's avatar image

    // Metadata
    created_at?: string;
    updated_at?: string;
}
