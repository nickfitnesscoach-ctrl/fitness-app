/**
 * Trainer Panel domain types (SSOT)
 *
 * Rule:
 * - Backend NEVER returns 'client' as status.
 * - 'client' is UI-only derived state.
 */

export type ApplicationStatusApi = 'new' | 'viewed' | 'contacted';
export type ApplicationStatusUi = ApplicationStatusApi | 'client';

export interface BodyTypeInfo {
  id: number;
  description: string;
  image_url: string;
}

/**
 * Raw details from backend API (strict)
 */
export interface ClientDetailsApi {
  age?: number;
  gender?: 'male' | 'female';
  height?: number;
  weight?: number;
  target_weight?: number;
  activity_level?: string;
  training_level?: string;
  goals?: string[];

  health_restrictions?: string[];

  current_body_type?: number;
  ideal_body_type?: number;

  timezone?: string;

  // optional diet fields from backend
  diet_type?: string;
  meals_per_day?: number;
  allergies?: string[] | string;
  disliked_food?: string;
  supplements?: string;
}

/**
 * UI-ready details (after transform)
 * NOTE: This is what components should consume.
 */
export interface ClientDetailsUi {
  age?: number;
  gender?: string; // localized string for UI ("Мужской"/"Женский"/"—")
  height?: number;
  weight?: number;
  target_weight?: number;
  activity_level?: string; // localized
  training_level?: string; // localized
  goals: string[];
  limitations: string[];

  body_type?: BodyTypeInfo;
  desired_body_type?: BodyTypeInfo;

  timezone?: string;

  diet_type?: string;
  meals_per_day?: number;
  allergies: string[]; // normalized
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
  details: ClientDetailsApi;
}

/**
 * UI model for application/client card.
 * `date` is UI formatted from created_at.
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
  date?: string;
  details: ClientDetailsUi;
}

export type ApplicationDetails = ClientDetailsUi;
