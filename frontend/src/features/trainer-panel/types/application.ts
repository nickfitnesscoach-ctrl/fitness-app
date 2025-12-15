/**
 * Trainer Panel domain types
 *
 * SSOT for trainer-panel types (UI + API response shapes).
 * IMPORTANT:
 * - Backend NEVER returns 'client' as status.
 * - 'client' is UI-only derived state.
 */

export type ApplicationStatusApi = 'new' | 'viewed' | 'contacted';
export type ApplicationStatusUi = ApplicationStatusApi | 'client';

/**
 * Body type info (UI-transformed)
 */
export interface BodyTypeInfo {
    id: number;
    description: string;
    image_url: string;
}

/**
 * Client details interface
 * 
 * Note: This interface supports BOTH API response fields AND UI-transformed fields.
 * - Backend sends: gender as 'male'|'female', current_body_type as number, health_restrictions
 * - UI transforms: gender to localized string, body_type to BodyTypeInfo, health_restrictions to limitations
 */
export interface ClientDetails {
    age?: number;
    // Gender can be either raw API value ('male'|'female') or localized UI string
    gender?: 'male' | 'female' | string;
    height?: number;
    weight?: number;
    target_weight?: number;
    activity_level?: string;
    training_level?: string;
    goals?: string[];

    // Backend field (raw API response)
    health_restrictions?: string[];
    // UI-transformed field (localized restrictions list)
    limitations?: string[];

    // Backend fields (raw API response - body type as number ID)
    current_body_type?: number;
    ideal_body_type?: number;

    // UI-transformed fields (rich body type info)
    body_type?: BodyTypeInfo;
    desired_body_type?: BodyTypeInfo;

    timezone?: string;

    // Diet-related fields (optional)
    diet_type?: string;
    meals_per_day?: number;
    allergies?: string[] | string;
    disliked_food?: string;
    supplements?: string;
}

/**
 * API response: strict status (no 'client')
 */
export interface ApplicationResponse {
    id: number;
    telegram_id: number;
    first_name: string;
    last_name?: string;
    username?: string;
    photo_url?: string;
    status: ApplicationStatusApi;
    created_at: string;
    details: ClientDetails;
}

/**
 * UI model: status can be extended to include 'client'
 * (derived locally when application converted to client)
 * 
 * Note: telegram_id and created_at are optional in UI model
 * because hooks may not include them in transformed data.
 * 'date' is added as UI-formatted date string (from created_at).
 */
export interface Application {
    id: number;
    telegram_id?: number;
    first_name: string;
    last_name?: string;
    username?: string;
    photo_url?: string;
    status?: ApplicationStatusUi;
    created_at?: string;
    date?: string;  // UI-formatted date string
    details: ClientDetails;
}

export interface ApplicationDetails extends ClientDetails { }
