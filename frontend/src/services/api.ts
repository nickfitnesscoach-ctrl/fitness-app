/**
 * API клиент для FoodMind WebApp
 *
 * Использует Header-based аутентификацию через Telegram WebApp.
 * JWT токены НЕ используются для WebApp (только headers).
 */

import { buildTelegramHeaders, getTelegramDebugInfo } from '../lib/telegram';

// ============================================================
// API URL Configuration
// ============================================================

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';
const API_TIMEOUT = 30000; // 30 seconds

const URLS = {
    // Telegram endpoints
    auth: `${API_BASE}/telegram/auth/`,
    applications: `${API_BASE}/telegram/applications/`,
    clients: `${API_BASE}/telegram/clients/`,
    inviteLink: `${API_BASE}/telegram/invite-link/`,
    subscribers: `${API_BASE}/telegram/subscribers/`,
    // Nutrition endpoints
    meals: `${API_BASE}/meals/`,
    goals: `${API_BASE}/nutrition/goals/`,
    calculateGoals: `${API_BASE}/nutrition/goals/calculate/`,
    setAutoGoals: `${API_BASE}/nutrition/goals/set-auto/`,
    // User endpoints
    profile: `${API_BASE}/users/profile/`,
    // Billing endpoints
    plan: `${API_BASE}/billing/plan`,
    // AI endpoints
    recognize: `${API_BASE}/ai/recognize/`,
};

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
        const response = await fetchWithTimeout(url, {
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

// ============================================================
// API Client
// ============================================================

export const api = {
    // Debug methods
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
            const response = await fetchWithTimeout(URLS.auth, {
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

    async createMeal(data: any) {
        try {
            const response = await fetchWithTimeout(URLS.meals, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify(data),
            });
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.detail || errorData.error || 'Failed to create meal');
            }
            return await response.json();
        } catch (error) {
            console.error('Error creating meal:', error);
            throw error;
        }
    },

    async addFoodItem(mealId: number, data: any) {
        try {
            const response = await fetchWithTimeout(`${URLS.meals}${mealId}/items/`, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify(data),
            });
            if (!response.ok) throw new Error('Failed to add food item');
            return await response.json();
        } catch (error) {
            console.error('Error adding food item:', error);
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
        log('Updating goals: ' + JSON.stringify(data));

        try {
            const response = await fetchWithTimeout(URLS.goals, {
                method: 'PUT',
                headers: getHeaders(),
                body: JSON.stringify({
                    calories: data.calories,
                    protein: data.protein,
                    fat: data.fat,
                    carbohydrates: data.carbohydrates,
                    source: 'MANUAL',
                    is_active: true,
                }),
            });

            log('Response status: ' + response.status);

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                log('Update goals error: ' + JSON.stringify(errorData));
                throw new Error(errorData.error || errorData.detail || 'Failed to update goals');
            }

            const result = await response.json();
            log('Goals updated successfully');
            return result;
        } catch (error) {
            console.error('Error updating goals:', error);
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

    // ========================================================
    // User Profile
    // ========================================================

    async getProfile() {
        try {
            const response = await fetchWithTimeout(URLS.profile, {
                headers: getHeaders(),
            });
            if (!response.ok) throw new Error('Failed to fetch profile');
            return await response.json();
        } catch (error) {
            console.error('Error fetching profile:', error);
            throw error;
        }
    },

    async updateProfile(data: any) {
        try {
            const response = await fetchWithTimeout(URLS.profile, {
                method: 'PATCH',
                headers: getHeaders(),
                body: JSON.stringify(data),
            });
            if (!response.ok) throw new Error('Failed to update profile');
            return await response.json();
        } catch (error) {
            console.error('Error updating profile:', error);
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

    // ========================================================
    // AI Recognition
    // ========================================================

    async recognizeFood(imageBase64: string, description?: string) {
        log('Calling AI recognize endpoint');
        try {
            const response = await fetchWithTimeout(URLS.recognize, {
                method: 'POST',
                headers: getHeaders(),
                body: JSON.stringify({
                    image: imageBase64,
                    description: description || '',
                }),
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.error || errorData.detail || `AI recognition failed (${response.status})`;
                log(`AI recognition error: ${errorMessage}`);
                throw new Error(errorMessage);
            }

            const result = await response.json();
            log(`AI recognized ${result.recognized_items?.length || 0} items`);
            return result;
        } catch (error) {
            console.error('AI recognition error:', error);
            throw error;
        }
    },
};
