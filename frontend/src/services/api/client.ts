/**
 * Base API Client
 * 
 * Provides core HTTP functionality:
 * - Fetch with timeout
 * - Retry with exponential backoff
 * - Global auth error handling (401/403)
 * - Telegram header injection
 */

import { buildTelegramHeaders, getTelegramDebugInfo } from '../../lib/telegram';
import { API_BASE_URL } from '../../config/env';

// ============================================================
// Configuration
// ============================================================

export const API_BASE = API_BASE_URL;
export const API_TIMEOUT = 150000; // 150 seconds
export const API_RETRY_ATTEMPTS = 3;
export const API_RETRY_DELAY = 1000; // ms

// ============================================================
// Error Classes
// ============================================================

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

/**
 * Unified API error format
 */
export interface ParsedApiError {
    code: string;
    message: string;
    details: Record<string, unknown>;
    status: number;
}

/**
 * Парсит ответ API в унифицированный формат ошибки.
 * Толерантен к разным форматам от backend:
 * - Новый: { error: { code, message, details } }
 * - Legacy 1: { error: "string" }
 * - Legacy 2: { detail: "string" }
 * - Legacy 3: { error: { code, message } } без details
 */
export function parseApiError(
    responseData: unknown,
    status: number,
    fallbackMessage = 'Произошла ошибка'
): ParsedApiError {
    // Новый формат: { error: { code, message, details } }
    if (
        typeof responseData === 'object' &&
        responseData !== null &&
        'error' in responseData
    ) {
        const errorField = (responseData as Record<string, unknown>).error;

        // Вложенный объект { code, message, details }
        if (typeof errorField === 'object' && errorField !== null) {
            const errObj = errorField as Record<string, unknown>;
            return {
                code: String(errObj.code || 'UNKNOWN_ERROR'),
                message: String(errObj.message || fallbackMessage),
                details: (errObj.details as Record<string, unknown>) || {},
                status,
            };
        }

        // Legacy: { error: "string" }
        if (typeof errorField === 'string') {
            return {
                code: errorField,
                message: errorField,
                details: {},
                status,
            };
        }
    }

    // Legacy DRF: { detail: "string" }
    if (
        typeof responseData === 'object' &&
        responseData !== null &&
        'detail' in responseData
    ) {
        const detail = (responseData as Record<string, unknown>).detail;
        return {
            code: 'API_ERROR',
            message: String(detail),
            details: {},
            status,
        };
    }

    // Fallback
    return {
        code: 'UNKNOWN_ERROR',
        message: fallbackMessage,
        details: {},
        status,
    };
}

export class ApiError extends Error {
    status: number;
    code: string;
    details: Record<string, unknown>;

    constructor(parsed: ParsedApiError);
    constructor(message: string, status: number, code?: string);
    constructor(
        messageOrParsed: string | ParsedApiError,
        status?: number,
        code?: string
    ) {
        if (typeof messageOrParsed === 'object') {
            super(messageOrParsed.message);
            this.status = messageOrParsed.status;
            this.code = messageOrParsed.code;
            this.details = messageOrParsed.details;
        } else {
            super(messageOrParsed);
            this.status = status || 0;
            this.code = code || 'UNKNOWN_ERROR';
            this.details = {};
        }
        this.name = 'ApiError';
    }

    /**
     * Проверяет, является ли ошибка определённым кодом
     */
    is(code: string): boolean {
        return this.code === code;
    }
}

/**
 * Обрабатывает не-OK ответ и выбрасывает ApiError
 */
export async function throwApiError(
    response: Response,
    fallbackMessage?: string
): Promise<never> {
    const data = await response.json().catch(() => ({}));
    const parsed = parseApiError(data, response.status, fallbackMessage);
    throw new ApiError(parsed);
}

// ============================================================
// Auth Error Events
// ============================================================

export type AuthErrorType = 'session_expired' | 'forbidden' | 'telegram_invalid';

export interface AuthErrorEvent {
    type: AuthErrorType;
    message: string;
    status: number;
}

export const dispatchAuthError = (event: AuthErrorEvent) => {
    log(`Auth error: ${event.type} - ${event.message}`);
    window.dispatchEvent(new CustomEvent('auth:error', { detail: event }));
};

export const onAuthError = (callback: (event: AuthErrorEvent) => void): (() => void) => {
    const handler = (e: Event) => {
        callback((e as CustomEvent<AuthErrorEvent>).detail);
    };
    window.addEventListener('auth:error', handler);
    return () => window.removeEventListener('auth:error', handler);
};

// ============================================================
// Debug Logging
// ============================================================

const debugLogs: string[] = [];

export const log = (msg: string) => {
    const timestamp = new Date().toISOString().split('T')[1];
    debugLogs.push(`${timestamp}: ${msg}`);
    if (debugLogs.length > 20) debugLogs.shift();
    console.log('[API]', msg);
};

export const getLogs = () => debugLogs;

export const getDebugInfo = () => ({
    ...getTelegramDebugInfo(),
    apiBase: API_BASE,
    logs: debugLogs,
});

// ============================================================
// Headers
// ============================================================

export const getHeaders = (): HeadersInit => {
    return buildTelegramHeaders();
};

export const getHeadersWithoutContentType = (): HeadersInit => {
    const headers = buildTelegramHeaders();
    delete (headers as Record<string, string>)['Content-Type'];
    return headers;
};

// ============================================================
// Auth Error Handler
// ============================================================

const handleAuthErrors = (response: Response): boolean => {
    if (response.status === 401) {
        dispatchAuthError({
            type: 'session_expired',
            message: 'Сессия истекла. Пожалуйста, откройте приложение заново из Telegram.',
            status: 401
        });
        return true;
    }

    if (response.status === 403) {
        dispatchAuthError({
            type: 'forbidden',
            message: 'Доступ запрещён. Попробуйте открыть приложение заново из Telegram.',
            status: 403
        });
        return true;
    }

    return false;
};

// ============================================================
// Fetch Functions
// ============================================================

export const fetchWithTimeout = async (
    url: string,
    options: RequestInit = {},
    timeout = API_TIMEOUT,
    skipAuthCheck = false,
    externalSignal?: AbortSignal
): Promise<Response> => {
    const timeoutController = new AbortController();
    const timeoutId = setTimeout(() => timeoutController.abort(), timeout);

    // Combine external signal with timeout signal
    let combinedSignal: AbortSignal;

    if (externalSignal) {
        // Use AbortSignal.any if available (modern browsers)
        if ('any' in AbortSignal) {
            combinedSignal = (AbortSignal as any).any([externalSignal, timeoutController.signal]);
        } else {
            // Fallback: create a new controller that aborts on either signal
            const combinedController = new AbortController();

            const abortCombined = () => combinedController.abort();
            externalSignal.addEventListener('abort', abortCombined);
            timeoutController.signal.addEventListener('abort', abortCombined);

            // Check if already aborted
            if (externalSignal.aborted) {
                combinedController.abort();
            }

            combinedSignal = combinedController.signal;
        }
    } else {
        combinedSignal = timeoutController.signal;
    }

    try {
        const response = await fetch(url, {
            ...options,
            signal: combinedSignal,
        });
        clearTimeout(timeoutId);

        if (!skipAuthCheck) {
            handleAuthErrors(response);
        }

        return response;
    } catch (error) {
        clearTimeout(timeoutId);

        // Check if aborted by external signal (user cancellation)
        if (externalSignal?.aborted) {
            // Re-throw as AbortError for caller to handle
            const abortError = new Error('Request cancelled');
            abortError.name = 'AbortError';
            throw abortError;
        }

        // Timeout abort
        if (error instanceof Error && error.name === 'AbortError') {
            throw new ApiError({
                code: 'TIMEOUT',
                message: `Превышено время ожидания (${Math.round(timeout / 1000)}с)`,
                details: { timeout },
                status: 0,
            });
        }
        throw error;
    }
};

export const fetchWithRetry = async (
    url: string,
    options: RequestInit = {},
    retries = API_RETRY_ATTEMPTS
): Promise<Response> => {
    let lastError: Error | null = null;

    for (let attempt = 0; attempt <= retries; attempt++) {
        try {
            const response = await fetchWithTimeout(url, options);

            // ✅ 429: не ретраим вслепую
            if (response.status === 429) return response;

            if (response.ok || (response.status >= 400 && response.status < 500)) {
                return response;
            }
        } catch (error) {
            lastError = error instanceof Error ? error : new Error(String(error));

            if (attempt >= retries) {
                throw lastError;
            }

            const delay = API_RETRY_DELAY * Math.pow(2, attempt);
            log(`Network error, retry ${attempt + 1}/${retries} after ${delay}ms: ${lastError.message}`);
            await new Promise(resolve => setTimeout(resolve, delay));
        }
    }

    throw lastError || new Error('Unknown error');
};

// ============================================================
// Error Response Parser
// ============================================================

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

export const parseErrorResponse = async (response: Response, fallback: string): Promise<string> => {
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
    } catch {
        return fallback;
    }
};

// ============================================================
// Image URL Helper
// ============================================================

export const resolveImageUrl = (url: string | null | undefined): string | null => {
    if (!url) return null;

    if (url.includes('backend:8000')) {
        return url.replace(/^http?:\/\/backend:8000/, '');
    }

    if (url.includes('localhost:8000') && !window.location.hostname.includes('localhost')) {
        return url.replace(/^http?:\/\/localhost:8000/, '');
    }

    if (url.startsWith('http')) return url;

    if (API_BASE.startsWith('http')) {
        try {
            const urlObj = new URL(API_BASE);
            return `${urlObj.origin}${url}`;
        } catch {
            return url;
        }
    }

    return url;
};
