/**
 * API клиент для FoodMind WebApp
 *
 * Использует Header-based аутентификацию через Telegram WebApp.
 * JWT токены НЕ используются для WebApp (только headers).
 */

import { buildTelegramHeaders, getTelegramDebugInfo } from '../lib/telegram';
import { Profile } from '../types/profile';
import { BillingMe, CreatePaymentRequest, CreatePaymentResponse, SubscriptionDetails, PaymentMethod, PaymentHistory, SubscriptionPlan } from '../types/billing';

export interface TrainerPanelAuthResponse {
    ok: boolean;
    user_id: number;
    role: 'admin';
}

// ============================================================
// Nutrition Types
// ============================================================

export interface Meal {
    id: number;
    meal_type: 'BREAKFAST' | 'LUNCH' | 'DINNER' | 'SNACK';
    meal_type_display?: string;
    date: string; // YYYY-MM-DD
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
    date: string; // YYYY-MM-DD
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

// Custom error classes for better error handling
export class UnauthorizedError extends Error {
    constructor(message: string = 'Unauthorized') {
        super(message);
        this.name = 'UnauthorizedError';
    }
}

export class ForbiddenError extends Error {
    constructor(message: string = 'Forbidden') {
        super(message);
        this.name = 'ForbiddenError';
    }
}

// ============================================================
// API URL Configuration
// ============================================================

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';
const TRAINER_PANEL_AUTH_URL = import.meta.env.VITE_TRAINER_PANEL_AUTH_URL || '/api/v1/trainer-panel/auth/';
const API_TIMEOUT = 150000; // 150 seconds
const API_RETRY_ATTEMPTS = 3; // Number of retry attempts
const API_RETRY_DELAY = 1000; // Initial delay between retries (ms)

const URLS = {
    // Telegram endpoints
    auth: `${API_BASE}/telegram/auth/`,
    trainerPanelAuth: TRAINER_PANEL_AUTH_URL,
    applications: `${API_BASE}/telegram/applications/`,
    clients: `${API_BASE}/telegram/clients/`,
    inviteLink: `${API_BASE}/telegram/invite-link/`,
    subscribers: `${API_BASE}/telegram/subscribers/`,
    // Nutrition endpoints
    meals: `${API_BASE}/meals/`,
    goals: `${API_BASE}/goals/`,
    calculateGoals: `${API_BASE}/goals/calculate/`,
    setAutoGoals: `${API_BASE}/goals/set-auto/`,
    weeklyStats: `${API_BASE}/stats/weekly/`,
    // User endpoints
    profile: `${API_BASE}/users/profile/`,
    uploadAvatar: `${API_BASE}/users/profile/avatar/`,
    // Billing endpoints
    plan: `${API_BASE}/billing/plan`,
    billingMe: `${API_BASE}/billing/me/`,
    createPayment: `${API_BASE}/billing/create-payment/`,
    cancelSubscription: `${API_BASE}/billing/cancel/`,
    resumeSubscription: `${API_BASE}/billing/resume/`,
    paymentMethods: `${API_BASE}/billing/payment-methods/`,
    // NEW: Settings screen endpoints
    subscriptionDetails: `${API_BASE}/billing/subscription/`,
    subscriptionAutoRenew: `${API_BASE}/billing/subscription/autorenew/`,
    paymentMethodDetails: `${API_BASE}/billing/payment-method/`,
    paymentsHistory: `${API_BASE}/billing/payments/`,
    bindCardStart: `${API_BASE}/billing/bind-card/start/`,
    plans: `${API_BASE}/billing/plans/`,
    // AI endpoints
    recognize: `${API_BASE}/ai/recognize/`,
    // mealAnalysis: (id: number) => `${API_BASE}/diary/meals/${id}/analysis/`, // REMOVED: Use URLS.meals + id
};

// ============================================================
// Meal Analysis Types
// ============================================================

export interface RecognizedItemAnalysis {
    id: number;
    name: string;
    amount_grams: number;
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number; // In JSON it was "carbs" but usually we use "carbohydrates" or map it. 
    // User JSON says "carbs". I should probably map it or use "carbs".
    // Let's use "carbs" to match the JSON exactly if I can, or map it.
    // The user JSON: "carbs": 48.3.
    // My existing types use "carbohydrates".
    // I will define it as "carbs" here to match the expected JSON, 
    // but I might want to map it to "carbohydrates" for consistency in UI if I reuse components.
    // Let's stick to the JSON structure for the type.
    carbs: number;
}

export interface MealAnalysis {
    id: number;
    photo_url: string | null;
    label: string;
    recognized_items: RecognizedItemAnalysis[];
}

// ============================================================
// Debug Logging
// ============================================================

const debugLogs: string[] = [];

const log = (msg: string) => {
    const timestamp = new Date().toISOString().split('T')[1];
    debugLogs.push(`${timestamp}: ${msg}`);
    if (debugLogs.length > 20) debugLogs.shift();
    console.log('[API]', msg);
};

const FIELD_LABELS: Record<string, string> = {
    avatar: 'Аватар',
    birth_date: 'Дата рождения',
    gender: 'Пол',
    height: 'Рост',
    weight: 'Вес',
    activity_level: 'Уровень активности',
    goal_type: 'Цель',
    timezone: 'Часовой пояс',
};

const parseErrorResponse = async (response: Response, fallback: string) => {
    const responseText = await response.text();

    if (!responseText) return fallback;

    try {
        const data = JSON.parse(responseText);

        if (typeof data.detail === 'string') return data.detail;
        if (typeof data.error === 'string') return data.error;

        const fieldMessages: string[] = [];
        Object.entries(data).forEach(([field, messages]) => {
            if (['detail', 'error', 'code'].includes(field)) return;

            const label = FIELD_LABELS[field] || field;

            if (Array.isArray(messages)) {
                fieldMessages.push(`${label}: ${messages.join(' ')}`);
            } else if (typeof messages === 'string') {
                fieldMessages.push(`${label}: ${messages}`);
            }
        });

        if (fieldMessages.length > 0) {
            return fieldMessages.join(' ');
        }

        return fallback;
    } catch (parseError) {
        console.warn('Failed to parse error response', parseError);
        return fallback;
    }
};

// ============================================================
// Helper Functions
// ============================================================

/**
 * Получение заголовков для API запросов
 * Использует централизованную функцию из telegram.ts
 */
const getHeaders = (): HeadersInit => {
    return buildTelegramHeaders();
};

/**
 * Fetch с timeout
 */
const fetchWithTimeout = async (url: string, options: RequestInit = {}, timeout = API_TIMEOUT): Promise<Response> => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
        const response = await fetch(url, {
            ...options,
            signal: controller.signal,
        });
        clearTimeout(timeoutId);
        return response;
    } catch (error) {
        clearTimeout(timeoutId);
        if (error instanceof Error && error.name === 'AbortError') {
            throw new Error(`Request timeout after ${timeout}ms`);
        }
        throw error;
    }
};

/**
 * Fetch с retry и exponential backoff
 * Автоматически повторяет запрос при ошибках сети и 5xx
 */
const fetchWithRetry = async (
    url: string,
    options: RequestInit = {},
    retries = API_RETRY_ATTEMPTS
): Promise<Response> => {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            const response = await fetchWithTimeout(url, options);

            // Успешный ответ или клиентская ошибка (4xx) - не retry
            if (response.ok || (response.status >= 400 && response.status < 500)) {
                return response;
            }

            // 5xx ошибка - retry
            if (attempt < retries) {
                const delay = API_RETRY_DELAY * Math.pow(2, attempt); // Exponential backoff
                log(`Retry ${attempt + 1}/${retries} after ${delay}ms for ${url} (status: ${response.status})`);
                await new Promise(resolve => setTimeout(resolve, delay));
                continue;
            }

            return response; // Last attempt, return error response
        } catch (error) {
            lastError = error instanceof Error ? error : new Error(String(error));

            // Последняя попытка - бросаем ошибку
            if (attempt >= retries) {
                throw lastError;
            }

            // Retry после задержки
            const delay = API_RETRY_DELAY * Math.pow(2, attempt);
            log(`Network error, retry ${attempt + 1}/${retries} after ${delay}ms: ${lastError.message}`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }

    throw lastError || new Error('Unknown error');
};

// ============================================================
// API Client
// ============================================================

// Helper to resolve image URLs
export const resolveImageUrl = (url: string | null | undefined): string | null => {
    if (!url) return null;

    // Handle internal Docker URLs (strip backend:8000)
    if (url.includes('backend:8000')) {
        return url.replace(/^http?:\/\/backend:8000/, '');
    }

    // Handle localhost URLs if we are in production (strip localhost:8000)
    // This ensures that if backend returns localhost URL but we are on domain.com, it becomes relative
    if (url.includes('localhost:8000') && !window.location.hostname.includes('localhost')) {
        return url.replace(/^http?:\/\/localhost:8000/, '');
    }

    if (url.startsWith('http')) return url;

    // If API_BASE is absolute (e.g. http://localhost:8000/api/v1), use its origin
    if (API_BASE.startsWith('http')) {
        try {
            const urlObj = new URL(API_BASE);
            return `${urlObj.origin}${url}`;
        } catch (e) {
            console.error('Error parsing API_BASE:', e);
            return url;
        }
    }

    return url;
};

export const api = {
    getLogs() {
        return debugLogs;
    },

    getDebugInfo() {
        return {
            ...getTelegramDebugInfo(),
            apiBase: API_BASE,
            logs: debugLogs,
        };
    },

    // ========================================================
    // Legacy JWT methods (NO-OP for WebApp, kept for compatibility)
    // ========================================================

    /**
     * @deprecated WebApp использует Header auth, JWT не нужен
     */
    setAccessToken(_token: string) {
        log('setAccessToken called (ignored - WebApp uses Header auth)');
    },

    /**
     * @deprecated WebApp использует Header auth
     */
    getAccessToken() {
        return null;
    },

    /**
     * @deprecated WebApp использует Header auth
     */
    clearToken() {
        // No-op
    },

    // ========================================================
    // Auth - для получения user info (JWT игнорируется)
    // ========================================================

    async authenticate(initData: string) {
        log('Authenticating with Telegram initData');
        try {
            const response = await fetchWithRetry(URLS.auth, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Telegram-Init-Data': initData,
                },
                body: JSON.stringify({ initData }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error || `Authentication failed (${response.status})`);
            }

            const data = await response.json();
            log(`Authenticated user: ${data.user?.telegram_id}`);

            // NOTE: JWT токены (data.access, data.refresh) игнорируются
            // WebApp использует Header auth через X-Telegram-* headers

            return data;
        } catch (error) {
            console.error('Authentication error:', error);
            throw error;
        }
    },

    async trainerPanelAuth(initData: string): Promise<TrainerPanelAuthResponse> {
        log('Authorizing trainer panel via Telegram WebApp');

        const response = await fetchWithRetry(URLS.trainerPanelAuth, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ init_data: initData }),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const detail = (errorData as { detail?: string }).detail;
            throw new Error(detail || `Trainer panel auth failed (${response.status})`);
        }

        return response.json() as Promise<TrainerPanelAuthResponse>;
    },

    // ========================================================
    // Telegram Admin Endpoints
    // ========================================================

    async getApplications() {
        try {
            const response = await fetchWithTimeout(URLS.applications, {
                headers: getHeaders(),
            });
            if (!response.ok) throw new Error('Failed to fetch applications');
            return await response.json();
        } catch (error) {
            console.error('Error fetching applications:', error);
            return [];
        }
    },

    async getClients() {
        try {
            const response = await fetchWithTimeout(URLS.clients, {
                headers: getHeaders(),
            });
            if (!response.ok) throw new Error('Failed to fetch clients');
            return await response.json();
        } catch (error) {
            console.error('Error fetching clients:', error);
            return [];
        }
    },

    async addClient(clientId: number) {
        try {
            const response = await fetchWithTimeout(`${URLS.clients}${clientId}/add/`, {
                method: 'POST',
                headers: getHeaders(),
            });
            if (!response.ok) throw new Error('Failed to add client');
            return await response.json();
        } catch (error) {
            console.error('Error adding client:', error);
            throw error;
        }
    },

    async removeClient(clientId: number) {
        try {
            const response = await fetchWithTimeout(`${URLS.clients}${clientId}/`, {
                method: 'DELETE',
                headers: getHeaders(),
            });
            if (!response.ok) throw new Error('Failed to remove client');
            return true;
        } catch (error) {
            console.error('Error removing client:', error);
            throw error;
        }
    },

    async deleteApplication(applicationId: number) {
        try {
            const response = await fetchWithTimeout(`${URLS.applications}${applicationId}/`, {
                method: 'DELETE',
                headers: getHeaders(),
            });
            if (!response.ok) throw new Error('Failed to delete application');
            return true;
        } catch (error) {
            console.error('Error deleting application:', error);
            throw error;
        }
    },

    async updateApplicationStatus(applicationId: number, status: 'new' | 'viewed' | 'contacted') {
        try {
            const response = await fetchWithTimeout(`${URLS.applications}${applicationId}/status/`, {
                method: 'PATCH',
                headers: getHeaders(),
                body: JSON.stringify({ status }),
            });
            if (!response.ok) throw new Error('Failed to update status');
            return await response.json();
        } catch (error) {
            console.error('Error updating status:', error);
            throw error;
        }
    },

    async getInviteLink() {
        try {
            const response = await fetchWithTimeout(URLS.inviteLink, {
                headers: getHeaders(),
            });
            if (!response.ok) throw new Error('Failed to fetch invite link');
            const data = await response.json();
            return data.link;
        } catch (error) {
            console.error('Error fetching invite link:', error);
            return 'https://t.me/Fit_Coach_bot?start=default';
        }
    },

    async getSubscribers() {
        try {
            const response = await fetchWithTimeout(URLS.subscribers, {
                headers: getHeaders(),
            });
            if (!response.ok) throw new Error('Failed to fetch subscribers');
            return await response.json();
        } catch (error) {
            console.error('Error fetching subscribers:', error);
            return { subscribers: [], stats: { total: 0, free: 0, monthly: 0, yearly: 0, revenue: 0 } };
        }
    },

    // ========================================================
    // Nutrition - Meals
    // ========================================================

    async getMeals(date: string) {
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
    },

    async createMeal(data: CreateMealRequest): Promise<Meal> {
        log(`Creating meal: ${data.meal_type
            } for ${data.date}`);
        try {
            const response = await fetchWithRetry(URLS.meals, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify(data),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMsg = errorData.detail || errorData.error || `Failed to create meal(${response.status})`;
                log(`Create meal error: ${errorMsg} `);
                throw new Error(errorMsg);
            }

            const meal = await response.json();
            log(`Meal created successfully: id = ${meal.id} `);
            return meal;
        } catch (error) {
            console.error('Error creating meal:', error);
            throw error;
        }
    },

    async addFoodItem(mealId: number, data: CreateFoodItemRequest): Promise<FoodItem> {
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
                log(`Add food item error: ${errorMsg} `);
                throw new Error(errorMsg);
            }

            const foodItem = await response.json();
            log(`Food item added successfully: id = ${foodItem.id} `);
            return foodItem;
        } catch (error) {
            console.error('Error adding food item:', error);
            throw error;
        }
    },

    async getMealAnalysis(id: number): Promise<MealAnalysis> {
        try {
            // Use existing endpoint /api/v1/meals/{id}/
            const response = await fetchWithTimeout(`${URLS.meals}${id}/`, {
                headers: getHeaders(),
            });
            if (!response.ok) throw new Error('Failed to fetch meal analysis');

            const data = await response.json();

            // Map MealSerializer response to MealAnalysis
            // Use meal photo_url if available, otherwise fallback to first item photo (legacy)
            const mainPhoto = data.photo_url || data.items?.find((item: any) => item.photo)?.photo || null;

            return {
                id: data.id,
                photo_url: resolveImageUrl(mainPhoto),
                label: data.meal_type_display,
                recognized_items: data.items.map((item: any) => ({
                    id: item.id,
                    name: item.name,
                    amount_grams: item.grams,
                    calories: item.calories,
                    protein: item.protein,
                    fat: item.fat,
                    carbs: item.carbohydrates
                }))
            };
        } catch (error) {
            console.error('Error fetching meal analysis:', error);
            throw error;
        }
    },

    async deleteMeal(id: number): Promise<void> {
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
    },

    async deleteFoodItem(mealId: number, itemId: number): Promise<void> {
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
    },

    async updateFoodItem(mealId: number, itemId: number, data: { name?: string; amount_grams?: number }): Promise<any> {
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
    },

    // ========================================================
    // Nutrition - Goals
    // ========================================================

    async getDailyGoals() {
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
    },

    async updateGoals(data: any) {
        const requestData = {
            calories: data.calories,
            protein: data.protein,
            fat: data.fat,
            carbohydrates: data.carbohydrates,
            source: 'MANUAL',
            is_active: true,
        };

        log('[Goals] Updating goals with data: ' + JSON.stringify(requestData));
        log('[Goals] Target URL: ' + URLS.goals);

        const headers = getHeaders();
        log('[Goals] Headers: ' + JSON.stringify({
            ...headers,
            'X-Telegram-Init-Data': (headers as any)['X-Telegram-Init-Data'] ? '[SET]' : '[NOT SET]'
        }));

        try {
            const response = await fetchWithRetry(URLS.goals, {
                method: 'PUT',
                headers: headers,
                body: JSON.stringify(requestData),
            });

            log('[Goals] Response status: ' + response.status);

            if (!response.ok) {
                const errorText = await response.text();
                let errorData: any = {};
                try {
                    errorData = JSON.parse(errorText);
                } catch {
                    errorData = { raw: errorText };
                }

                log('[Goals] Update error: ' + JSON.stringify(errorData));

                // Provide detailed error messages
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
    },

    async calculateGoals() {
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
    },

    async setAutoGoals() {
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
    },

    async getWeeklyStats(startDate: string) {
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
    },

    // ========================================================
    // User Profile
    // ========================================================

    async getProfile(): Promise<Profile> {
        try {
            const response = await fetchWithTimeout(URLS.profile, {
                headers: getHeaders(),
            });
            if (!response.ok) throw new Error('Failed to fetch profile');
            const userData = await response.json();
            // Backend returns UserSerializer {id, username, email, profile: {...}}
            // Extract profile field
            return userData.profile || userData;
        } catch (error) {
            console.error('Error fetching profile:', error);
            throw error;
        }
    },

    async updateProfile(data: Partial<Profile>): Promise<Profile> {
        try {
            const response = await fetchWithTimeout(URLS.profile, {
                method: 'PATCH',
                headers: getHeaders(),
                body: JSON.stringify(data),
            });
            if (!response.ok) {
                const message = await parseErrorResponse(response, 'Не удалось сохранить профиль');
                throw new Error(message);
            }
            const userData = await response.json();
            // Backend returns UserSerializer {id, username, email, profile: {...}}
            // Extract profile field
            return userData.profile || userData;
        } catch (error) {
            console.error('Error updating profile:', error);
            throw error;
        }
    },

    async uploadAvatar(file: File): Promise<Profile> {
        try {
            // Create FormData for multipart/form-data upload
            const formData = new FormData();
            formData.append('avatar', file);

            // Get headers without Content-Type (browser will set it automatically for FormData)
            const headers = buildTelegramHeaders();
            // Remove Content-Type to let browser set it with boundary
            delete (headers as any)['Content-Type'];

            log(`Uploading avatar: ${file.name
                }(${(file.size / 1024).toFixed(1)} KB)`);

            const response = await fetchWithTimeout(URLS.uploadAvatar, {
                method: 'POST',
                headers: headers,
                body: formData,
            });

            if (!response.ok) {
                // Handle authentication errors specifically
                if (response.status === 401) {
                    log('Avatar upload failed: Unauthorized (401)');
                    throw new UnauthorizedError('Сессия истекла. Пожалуйста, откройте приложение заново из Telegram.');
                }

                if (response.status === 403) {
                    log('Avatar upload failed: Forbidden (403)');
                    throw new ForbiddenError('Доступ запрещен. Пожалуйста, откройте приложение заново из Telegram.');
                }

                // Handle other errors
                const errorMessage = await parseErrorResponse(response, 'Не удалось загрузить фото');
                log(`Avatar upload failed: ${errorMessage} `);
                throw new Error(errorMessage);
            }

            const userData = await response.json();
            log('Avatar uploaded successfully');
            // Backend returns UserSerializer {id, username, email, profile: {...}}
            // Extract profile field
            return userData.profile || userData;
        } catch (error) {
            console.error('Error uploading avatar:', error);
            throw error;
        }
    },

    // ========================================================
    // Billing
    // ========================================================

    async getSubscriptionPlan() {
        try {
            const response = await fetchWithTimeout(URLS.plan, {
                headers: getHeaders(),
            });
            if (!response.ok) throw new Error('Failed to fetch plan');
            return await response.json();
        } catch (error) {
            console.error('Error fetching plan:', error);
            return null;
        }
    },

    /**
     * GET /api/v1/billing/plans/
     * Получение списка доступных тарифов
     */
    async getSubscriptionPlans(): Promise<SubscriptionPlan[]> {
        try {
            const response = await fetchWithTimeout(URLS.plans, {
                headers: getHeaders(),
            });
            if (!response.ok) throw new Error('Failed to fetch subscription plans');
            return await response.json();
        } catch (error) {
            console.error('Error fetching subscription plans:', error);
            throw error;
        }
    },

    /**
     * GET /api/v1/billing/me/
     * Получение статуса подписки с лимитами и использованием
     */
    async getBillingMe(): Promise<BillingMe> {
        log('Fetching billing status');
        try {
            const response = await fetchWithRetry(URLS.billingMe, {
                headers: getHeaders(),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                log(`Billing status error: ${response.status} `);
                throw new Error(errorData.detail || errorData.error || 'Failed to fetch billing status');
            }

            const data = await response.json();
            log(`Billing status: plan = ${data.plan_code}, limit = ${data.daily_photo_limit}, used = ${data.used_today} `);
            return data;
        } catch (error) {
            console.error('Error fetching billing status:', error);
            throw error;
        }
    },

    /**
     * POST /api/v1/billing/create-payment/
     * Создание платежа для подписки
     */
    async createPayment(request: CreatePaymentRequest): Promise<CreatePaymentResponse> {
        log(`Creating payment for plan: ${request.plan_code} `);
        try {
            const response = await fetchWithRetry(URLS.createPayment, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify(request),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                log(`Payment creation error: ${errorData.error?.code || response.status} `);
                throw new Error(errorData.error?.message || errorData.detail || 'Failed to create payment');
            }

            const data = await response.json();
            log(`Payment created: ${data.payment_id} `);
            return data;
        } catch (error) {
            console.error('Error creating payment:', error);
            throw error;
        }
    },

    /**
     * POST /api/v1/billing/cancel/
     * Отключение автопродления
     */
    async cancelSubscription() {
        log('Canceling subscription auto-renew');
        try {
            const response = await fetchWithRetry(URLS.cancelSubscription, {
                method: 'POST',
                headers: getHeaders(),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Failed to cancel subscription');
            }

            return await response.json();
        } catch (error) {
            console.error('Error canceling subscription:', error);
            throw error;
        }
    },

    /**
     * POST /api/v1/billing/resume/
     * Включение автопродления
     */
    async resumeSubscription() {
        log('Resuming subscription auto-renew');
        try {
            const response = await fetchWithRetry(URLS.resumeSubscription, {
                method: 'POST',
                headers: getHeaders(),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || 'Failed to resume subscription');
            }

            return await response.json();
        } catch (error) {
            console.error('Error resuming subscription:', error);
            throw error;
        }
    },

    /**
     * GET /api/v1/billing/payment-methods/
     * Получение методов оплаты (если нужно отдельно)
     */
    async getPaymentMethods() {
        // ... implementation if needed
    },

    /**
     * Инициация привязки карты
     * Создает платёж для подписки, который автоматически сохраняет карту (backend всегда save_payment_method=true)
     */
    /**
     * POST /api/v1/billing/bind-card/start/
     * Запуск процесса привязки карты (платёж 1₽)
     */
    async bindCard() {
        log('Starting card binding flow (1₽ payment)');
        try {
            const response = await fetchWithRetry(URLS.bindCardStart, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({}),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                log(`Card binding error: ${errorData.error?.code || response.status} `);

                // Возвращаем структурированную ошибку
                const errorMessage = errorData.error?.message || errorData.detail || 'Не удалось запустить привязку карты';
                const errorCode = errorData.detail || errorData.error?.code || 'UNKNOWN_ERROR';

                throw new Error(JSON.stringify({
                    message: errorMessage,
                    code: errorCode
                }));
            }

            const data = await response.json();
            log(`Card binding payment created: ${data.payment_id} `);

            // Открываем платёжную форму в Telegram WebApp или браузере
            const isTMA = typeof window !== 'undefined' && window.Telegram?.WebApp?.initData;
            if (isTMA && window.Telegram) {
                window.Telegram.WebApp.openLink(data.confirmation_url);
            } else {
                window.location.href = data.confirmation_url;
            }

            return data;
        } catch (error) {
            console.error('Error initiating card binding:', error);
            throw error;
        }
    },

    /**
     * @deprecated Use bindCard() instead
     * Legacy method for backwards compatibility
     */
    async addPaymentMethod() {
        return this.bindCard();
    },

    /**
     * POST /api/v1/billing/create-test-live-payment/
     * Создание тестового платежа за 1₽ на боевом магазине YooKassa
     * ДОСТУП: Только для админов
     */
    async createTestLivePayment() {
        log('Creating test live payment (admin only)');
        try {
            const response = await fetchWithRetry(URLS.createPayment.replace('create-payment', 'create-test-live-payment'), {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({}),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.error?.message || errorData.detail || 'Не удалось создать тестовый платёж');
            }

            const data = await response.json();
            log(`Test payment created: ${data.payment_id}, mode: ${data.yookassa_mode} `);

            // Открываем платёжную форму
            const isTMA = typeof window !== 'undefined' && window.Telegram?.WebApp?.initData;
            if (isTMA && window.Telegram) {
                window.Telegram.WebApp.openLink(data.confirmation_url);
            } else {
                window.location.href = data.confirmation_url;
            }

            return data;
        } catch (error) {
            console.error('Error creating test payment:', error);
            throw error;
        }
    },

    /**
     * GET /api/v1/billing/subscription/
     * Получение полной информации о подписке для настроек
     */
    async getSubscriptionDetails(): Promise<SubscriptionDetails> {
        log('Fetching subscription details');
        try {
            const response = await fetchWithRetry(URLS.subscriptionDetails, {
                headers: getHeaders(),
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch subscription details: ${response.status} `);
            }

            const data = await response.json();
            log('Subscription details fetched successfully');
            return data;
        } catch (error) {
            log(`Failed to fetch subscription details: ${error} `);
            throw error;
        }
    },

    /**
     * POST /api/v1/billing/subscription/autorenew/
     * Включение/отключение автопродления
     */
    async setAutoRenew(enabled: boolean): Promise<SubscriptionDetails> {
        log(`Setting auto - renew: ${enabled} `);
        try {
            const response = await fetchWithRetry(URLS.subscriptionAutoRenew, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({ enabled }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error?.message || 'Failed to toggle auto-renew');
            }

            const data = await response.json();
            log('Auto-renew toggled successfully');
            return data;
        } catch (error) {
            log(`Failed to toggle auto - renew: ${error} `);
            throw error;
        }
    },

    /**
     * GET /api/v1/billing/payment-method/
     * Получение информации о привязанном способе оплаты
     */
    async getPaymentMethod(): Promise<PaymentMethod> {
        log('Fetching payment method');
        try {
            const response = await fetchWithRetry(URLS.paymentMethodDetails, {
                headers: getHeaders(),
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch payment method: ${response.status} `);
            }

            const data = await response.json();
            log('Payment method fetched successfully');
            return data;
        } catch (error) {
            log(`Failed to fetch payment method: ${error} `);
            throw error;
        }
    },

    /**
     * GET /api/v1/billing/payments/?limit=10
     * Получение истории платежей
     */
    async getPaymentsHistory(limit = 10): Promise<PaymentHistory> {
        log(`Fetching payments history(limit: ${limit})`);
        try {
            const response = await fetchWithRetry(`${URLS.paymentsHistory}?limit = ${limit} `, {
                headers: getHeaders(),
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch payments history: ${response.status} `);
            }

            const data = await response.json();
            log(`Payments history fetched: ${data.results.length} items`);
            return data;
        } catch (error) {
            log(`Failed to fetch payments history: ${error} `);
            throw error;
        }
    },

    // ========================================================
    // AI Recognition
    // ========================================================

    async recognizeFood(imageFile: File, description?: string, mealType?: string, date?: string) {
        log(`Calling AI recognize endpoint with file: ${imageFile.name} `);
        try {
            const formData = new FormData();
            formData.append('image', imageFile);
            if (description) {
                formData.append('description', description);
            }
            if (mealType) {
                formData.append('meal_type', mealType);
            }
            if (date) {
                formData.append('date', date);
            }

            // Debug: Verify FormData
            console.log('FormData check - image:', formData.get('image'));

            // Get headers without Content-Type (browser sets it with boundary)
            const headers = getHeaders();
            delete (headers as any)['Content-Type'];

            const response = await fetchWithTimeout(URLS.recognize, {
                method: 'POST',
                headers: headers,
                body: formData,
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                console.log('RECOGNIZE ERROR RESPONSE', response.status, errorData);
                log(`AI recognition error: ${errorData.error || errorData.detail || response.status} `);

                const error = new Error(errorData.detail || errorData.error || `AI recognition failed(${response.status})`);
                (error as any).error = errorData.error || 'UNKNOWN_ERROR';
                (error as any).detail = errorData.detail || error.message;
                (error as any).status = response.status;
                (error as any).data = errorData;
                throw error;
            }

            const backendResult = await response.json();
            console.log('RECOGNIZE OK', response.status, backendResult);
            log(`RAW AI response: ${JSON.stringify(backendResult)} `);

            // Backend returns: { recognized_items: [...], total_calories: ..., total_protein: ..., total_fat: ..., total_carbohydrates: ... }
            // Items already have correct field names: name, grams, calories, protein, fat, carbohydrates
            const mappedResult = {
                recognized_items: backendResult.recognized_items || [],
                total_calories: backendResult.total_calories || 0,
                total_protein: backendResult.total_protein || 0,
                total_fat: backendResult.total_fat || 0,
                total_carbohydrates: backendResult.total_carbohydrates || 0,
                meal_id: backendResult.meal_id,
                photo_url: backendResult.photo_url
            };

            log(`AI recognized ${mappedResult.recognized_items.length} items`);
            console.log('MAPPED RESULT', mappedResult);
            return mappedResult;
        } catch (error: any) {
            console.log(
                'RECOGNIZE ERROR CATCH',
                error?.message,
                error?.status,
                error?.data
            );
            console.error('AI recognition error:', error);
            throw error;
        }
    },
};
