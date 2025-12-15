/**
 * Auth API Module
 *
 * Handles Telegram authentication (who you are).
 * Trainer panel endpoints (what you can do as trainer) are in trainer.ts.
 *
 * @module services/api/auth
 */

import { fetchWithRetry, log } from './client';
import { URLS } from './urls';
import type { TrainerPanelAuthResponse, AuthResponse } from './types';

// ============================================================
// Authentication
// ============================================================

export const authenticate = async (initData: string): Promise<AuthResponse> => {
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
            throw new Error((errorData as { error?: string }).error || `Authentication failed (${response.status})`);
        }

        const data = (await response.json()) as AuthResponse;
        log(`Authenticated user: ${data.user?.telegram_id}`);
        return data;
    } catch (error) {
        console.error('Authentication error:', error);
        throw error;
    }
};

/**
 * Authorize user for trainer panel access (role check)
 * Note: belongs in auth.ts (authorization is auth concern)
 */
export const trainerPanelAuth = async (initData: string): Promise<TrainerPanelAuthResponse> => {
    log('Authorizing trainer panel via Telegram WebApp');

    const response = await fetchWithRetry(URLS.trainerPanelAuth, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            // Keep consistent with authenticate(): always send initData header
            'X-Telegram-Init-Data': initData,
        },
        // Keep body for backward compatibility with backend expectations
        body: JSON.stringify({ init_data: initData }),
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const detail = (errorData as { detail?: string }).detail;
        throw new Error(detail || `Trainer panel auth failed (${response.status})`);
    }

    return (await response.json()) as TrainerPanelAuthResponse;
};

// ============================================================
// ⚠️  DEPRECATED: Backward Compatibility Re-exports
// ============================================================
//
// These re-exports exist ONLY for backward compatibility.
// DO NOT import trainer functions from this file!
//
// ✅ Correct:  import { api } from 'services/api'; await api.getClients();
// ✅ Correct:  import { getClients } from 'services/api/trainer';
// ❌ Wrong:    import { getClients } from 'services/api/auth';
//
// @deprecated Will be removed in v2.0
export {
    getApplications,
    deleteApplication,
    updateApplicationStatus,
    getClients,
    addClient,
    removeClient,
    getInviteLink,
    getSubscribers,
} from './trainer';
