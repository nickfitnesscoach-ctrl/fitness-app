/**
 * Централизованный модуль для работы с Telegram WebApp
 *
 * Этот модуль обеспечивает:
 * - Единую точку инициализации Telegram WebApp
 * - Формирование auth headers для API запросов
 * - Debug режим через centralized configuration
 */

import { IS_DEBUG, DEBUG_USER } from '../shared/config/debug';

// ============================================================
// Types
// ============================================================

export interface TelegramUserInfo {
    id: number;
    first_name: string;
    last_name?: string;
    username?: string;
    language_code?: string;
    is_premium?: boolean;
}

export interface TelegramAuthData {
    initData: string;
    user: TelegramUserInfo;
}

// ============================================================
// Browser Debug Mode
// ============================================================

/**
 * Debug user для Browser Debug Mode
 * Uses centralized DEBUG_USER configuration
 */
const DEBUG_TELEGRAM_USER: TelegramUserInfo = DEBUG_USER;

/**
 * Проверяет, включён ли Debug Mode
 * Uses centralized IS_DEBUG configuration
 */
export function isDebugModeEnabled(): boolean {
    return IS_DEBUG;
}

/**
 * Проверяет, нужно ли использовать Debug Mode
 * (debug включён И нет реального Telegram WebApp)
 */
export function shouldUseDebugMode(): boolean {
    if (typeof window === 'undefined') return false;

    const hasTelegram = Boolean(window.Telegram?.WebApp?.initData);

    return IS_DEBUG && !hasTelegram;
}

/**
 * Проверка, включён ли Browser Debug Mode (legacy compatibility)
 * @deprecated Use IS_DEBUG from shared/config/debug instead
 */
export function isBrowserDebugMode(): boolean {
    return IS_DEBUG;
}

// ============================================================
// Internal State
// ============================================================

let _telegramAuthData: TelegramAuthData | null = null;
let _initPromise: Promise<TelegramAuthData | null> | null = null;
let _isBrowserDebug = false;

export function getTelegramWebApp(): any | null {
    if (typeof window === 'undefined') return null;
    return (window as any).Telegram?.WebApp || null;
}

/**
 * Проверка доступности Telegram WebApp
 */
export function isTelegramWebAppAvailable(): boolean {
    const tg = getTelegramWebApp();
    return Boolean(tg?.initData);
}

/**
 * Асинхронная инициализация Telegram WebApp
 * Вызывается ОДИН раз при старте приложения
 *
 * @returns Promise с данными авторизации или null
 */
export async function initTelegramWebApp(): Promise<TelegramAuthData | null> {
    // Если уже инициализировано - возвращаем кэш
    if (_telegramAuthData) {
        return _telegramAuthData;
    }

    // Если инициализация уже запущена - ждём её
    if (_initPromise) {
        return _initPromise;
    }

    _initPromise = _doInitTelegramWebApp();
    return _initPromise;
}

async function _doInitTelegramWebApp(): Promise<TelegramAuthData | null> {
    // Проверяем Browser Debug Mode
    if (isBrowserDebugMode()) {
        console.log('[Telegram] Browser Debug Mode enabled');
        _isBrowserDebug = true;
        _telegramAuthData = {
            initData: 'debug_mode_init_data',
            user: DEBUG_TELEGRAM_USER,
        };
        console.log('[Telegram] Debug user initialized:', DEBUG_TELEGRAM_USER.username);
        return _telegramAuthData;
    }

    const tg = getTelegramWebApp();

    // Telegram WebApp доступен
    if (tg?.initData && tg?.initDataUnsafe?.user) {
        // Вызываем ready() и expand()
        tg.ready();
        tg.expand();

        // Применяем тему
        applyTelegramTheme(tg);

        const user = tg.initDataUnsafe.user as TelegramUserInfo;

        _telegramAuthData = {
            initData: tg.initData,
            user: user,
        };

        console.log('[Telegram] Initialized:', {
            userId: user.id,
            username: user.username,
        });

        return _telegramAuthData;
    }

    // Telegram недоступен
    console.error('[Telegram] WebApp not available');
    return null;
}

/**
 * Получить текущие данные авторизации
 * ВАЖНО: Вызывайте после initTelegramWebApp()
 */
export function getTelegramAuthData(): TelegramAuthData | null {
    return _telegramAuthData;
}

/**
 * Проверить, инициализирован ли Telegram
 */
export function isTelegramInitialized(): boolean {
    return _telegramAuthData !== null;
}

// ============================================================
// Auth Headers для API
// ============================================================

/**
 * Формирование заголовков для API запросов
 * Единая функция для всех запросов к backend
 *
 * SECURITY: Debug Mode headers are only sent when:
 * 1. VITE_DEBUG_MODE=true in .env
 * 2. No real Telegram WebApp is available
 */
export function buildTelegramHeaders(): HeadersInit {
    if (!_telegramAuthData) {
        console.error('[Telegram] Headers requested but not initialized!');
        // Возвращаем пустые headers вместо throw - для graceful degradation
        return {
            'Content-Type': 'application/json',
        };
    }

    const { initData, user } = _telegramAuthData;

    // Browser Debug Mode - специальные заголовки
    // SECURITY: Only when explicitly enabled and no Telegram available
    if (_isBrowserDebug) {
        console.warn('[Auth] Using Debug Mode - payments disabled');
        return {
            'Content-Type': 'application/json',
            'X-Debug-Mode': 'true',
            'X-Debug-User-Id': String(user.id),
            'X-Telegram-ID': String(user.id),
            'X-Telegram-First-Name': encodeURIComponent(user.first_name || ''),
            'X-Telegram-Username': encodeURIComponent(user.username || ''),
        };
    }

    // Обычный Telegram режим
    return {
        'Content-Type': 'application/json',
        'X-Telegram-ID': String(user.id),
        'X-Telegram-First-Name': encodeURIComponent(user.first_name || ''),
        'X-Telegram-Username': encodeURIComponent(user.username || ''),
        'X-Telegram-Init-Data': initData,
    };
}

// ============================================================
// Legacy Functions (для совместимости)
// ============================================================

/**
 * @deprecated Используйте getTelegramAuthData().user
 */
export function getTelegramUser(): TelegramUserInfo | null {
    return _telegramAuthData?.user || null;
}

/**
 * @deprecated Используйте getTelegramAuthData().initData
 */
// eslint-disable-next-line @typescript-eslint/no-unused-vars
export function getTelegramInitData(_devMode = false): string | null {
    if (_telegramAuthData) {
        return _telegramAuthData.initData;
    }

    // Fallback для legacy кода
    const tg = getTelegramWebApp();
    if (tg?.initData) {
        return tg.initData;
    }



    return null;
}

/**
 * @deprecated Используйте getTelegramAuthData().user.id
 */
export function getTelegramUserId(): string | null {
    return _telegramAuthData?.user?.id ? String(_telegramAuthData.user.id) : null;
}

/**
 * @deprecated Используйте getTelegramAuthData().user.first_name
 */
export function getTelegramUserName(): string {
    return _telegramAuthData?.user?.first_name || 'User';
}

/**
 * @deprecated Используйте getTelegramAuthData().user.username
 */
export function getTelegramUsername(): string {
    return _telegramAuthData?.user?.username || '';
}

// ============================================================
// Theme & UI Functions
// ============================================================

/**
 * Применение темы Telegram к документу
 */
export function applyTelegramTheme(tg: any) {
    if (!tg?.themeParams) return;

    const themeVars: Record<string, string> = {
        '--tg-theme-bg-color': tg.themeParams.bg_color || '#ffffff',
        '--tg-theme-text-color': tg.themeParams.text_color || '#000000',
        '--tg-theme-button-color': tg.themeParams.button_color || '#2481cc',
        '--tg-theme-button-text-color': tg.themeParams.button_text_color || '#ffffff',
        '--tg-theme-secondary-bg-color': tg.themeParams.secondary_bg_color || '#f0f0f0',
        '--tg-theme-hint-color': tg.themeParams.hint_color || '#999999',
        '--tg-theme-link-color': tg.themeParams.link_color || '#2481cc',
    };

    Object.entries(themeVars).forEach(([key, value]) => {
        document.documentElement.style.setProperty(key, value);
    });
}

/**
 * Закрытие WebApp
 */
export function closeTelegramWebApp() {
    getTelegramWebApp()?.close();
}

/**
 * Открытие ссылки
 */
export function openTelegramLink(url: string) {
    getTelegramWebApp()?.openLink(url);
}

/**
 * Показать alert
 */
export function showTelegramAlert(message: string) {
    getTelegramWebApp()?.showAlert(message);
}

/**
 * Показать confirm
 */
export function showTelegramConfirm(message: string, callback?: (confirmed: boolean) => void) {
    const tg = getTelegramWebApp();
    if (tg) {
        tg.showConfirm(message, callback);
    }
}

// ============================================================
// Debug
// ============================================================

/**
 * Получение debug информации
 */
export function getTelegramDebugInfo() {
    const tg = getTelegramWebApp();
    return {
        available: !!tg,
        initialized: isTelegramInitialized(),
        initData: _telegramAuthData?.initData || null,
        user: _telegramAuthData?.user || null,
        platform: tg?.platform || null,
        version: tg?.version || null,
        colorScheme: tg?.colorScheme || null,
        devMode: false,
        browserDebugMode: _isBrowserDebug,
        debugModeEnabled: isDebugModeEnabled(),
        shouldUseDebug: shouldUseDebugMode(),
    };
}
