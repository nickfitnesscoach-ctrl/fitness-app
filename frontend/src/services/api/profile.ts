/**
 * Profile API Module
 * 
 * Handles user profile operations.
 */

import {
    fetchWithTimeout,
    fetchWithRetry,
    getHeaders,
    getHeadersWithoutContentType,
    parseErrorResponse,
    log,
    UnauthorizedError,
    ForbiddenError
} from './client';
import { URLS } from './urls';
import type { Profile } from '../../types/profile';

// ============================================================
// Profile
// ============================================================

export const getProfile = async (): Promise<Profile | null> => {
    try {
        const response = await fetchWithRetry(URLS.profile, {
            headers: getHeaders(),
        });

        // 429 handling: return null gracefully
        if (response.status === 429) {
            console.warn('[Profile] Rate limited (429), skipping profile load');
            return null;
        }

        if (!response.ok) throw new Error('Failed to fetch profile');
        const userData = await response.json();
        return userData.profile || userData;
    } catch (error) {
        console.error('Error fetching profile:', error);
        throw error; // Re-throw other errors
    }
};

export const updateProfile = async (data: Partial<Profile>): Promise<Profile> => {
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
        return userData.profile || userData;
    } catch (error) {
        console.error('Error updating profile:', error);
        throw error;
    }
};

export const uploadAvatar = async (file: File): Promise<Profile> => {
    try {
        const formData = new FormData();
        formData.append('avatar', file);

        const headers = getHeadersWithoutContentType();

        log(`Uploading avatar: ${file.name}(${(file.size / 1024).toFixed(1)} KB)`);

        const response = await fetchWithTimeout(URLS.uploadAvatar, {
            method: 'POST',
            headers: headers,
            body: formData,
        });

        if (!response.ok) {
            if (response.status === 401) {
                log('Avatar upload failed: Unauthorized (401)');
                throw new UnauthorizedError('Сессия истекла. Пожалуйста, откройте приложение заново из Telegram.');
            }

            if (response.status === 403) {
                log('Avatar upload failed: Forbidden (403)');
                throw new ForbiddenError('Доступ запрещен. Пожалуйста, откройте приложение заново из Telegram.');
            }

            const errorMessage = await parseErrorResponse(response, 'Не удалось загрузить фото');
            log(`Avatar upload failed: ${errorMessage}`);
            throw new Error(errorMessage);
        }

        const userData = await response.json();
        log('Avatar uploaded successfully');
        return userData.profile || userData;
    } catch (error) {
        console.error('Error uploading avatar:', error);
        throw error;
    }
};
