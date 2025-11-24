export type Sex = 'male' | 'female';

export type ActivityLevel = 'low' | 'moderate' | 'high' | 'athlete';

export type GoalType = 'loss' | 'maintenance' | 'gain';

export interface Profile {
    id: number;
    telegram_id: string;
    name: string;
    username?: string;
    sex?: Sex;
    birthdate?: string;
    height_cm?: number;
    weight_kg?: number;
    activity_level?: ActivityLevel;
    goal?: GoalType;
    timezone?: string;
    is_complete: boolean;
}

export interface NutritionTargets {
    calories: number;
    proteins_g: number;
    fats_g: number;
    carbs_g: number;
    formula: 'mifflin' | 'manual' | 'other';
    updated_at: string;
}
