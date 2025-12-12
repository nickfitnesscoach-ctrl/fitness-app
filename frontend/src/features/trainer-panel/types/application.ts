/**
 * Application Types
 * 
 * Types for trainer panel applications.
 */

export interface Application {
    id: number;
    username: string;
    first_name: string;
    date: string;
    status?: 'new' | 'viewed' | 'contacted';
    photo_url?: string;
    details: {
        age: number;
        gender: 'Мужской' | 'Женский';
        height: number;
        weight: number;
        target_weight: number;
        activity_level: string;
        training_level: string;
        goals: string[];
        limitations: string[];
        body_type: {
            id: number;
            description: string;
            image_url: string;
        };
        desired_body_type: {
            id: number;
            description: string;
            image_url: string;
        };
        diet_type: string;
        meals_per_day: number;
        allergies: string;
        disliked_food: string;
        supplements: string;
        timezone: string;
    }
}
