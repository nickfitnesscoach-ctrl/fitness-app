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
 * Uses centralized IS_DEBUG configuration (DEV only)
 */
export function isDebugModeEnabled(): boolean {
    return IS_DEBUG;
}

/**
 * Проверяет, нужно ли использовать Debug Mode
 * (DEV environment AND no real Telegram WebApp available)
 */
export function shouldUseDebugMode(): boolean {
    if (typeof window === 'undefined') return false;

    const hasTelegram = Boolean(window.Telegram?.WebApp?.initData);

    // Only use debug in DEV when Telegram is not available
    return IS_DEBUG && !hasTelegram;
}

// ============================================================
// Internal State
// ============================================================

let _telegramAuthData: TelegramAuthData | null = null;
let _initPromise: Promise<TelegramAuthData | null> | null = null;
let _isBrowserDebug = false;
let _didLogDebugPaymentsDisabled = false;

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
    const tg = getTelegramWebApp();

    // Telegram WebApp доступен
    if (tg?.initData && tg?.initDataUnsafe?.user) {
        // Вызываем ready() и expand()
        tg.ready();
        tg.expand();

        // Применяем тему
        applyTelegramTheme(tg);

        // Применяем safe-area insets
        applySafeAreaInsets(tg);

        // Подписываемся на динамические изменения safe-area
        subscribeToSafeAreaChanges(tg);

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

    // Telegram недоступен - проверяем Browser Debug Mode
    if (shouldUseDebugMode()) {
        console.log('[Telegram] Browser Debug Mode enabled (DEV only, no Telegram available)');
        _isBrowserDebug = true;
        _telegramAuthData = {
            initData: 'debug_mode_init_data',
            user: DEBUG_TELEGRAM_USER,
        };
        console.log('[Telegram] Debug user initialized:', DEBUG_TELEGRAM_USER.username);
        return _telegramAuthData;
    }

    // Telegram недоступен и не DEV
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
 * SECURITY: Debug Mode headers are only sent in DEV environment
 * Production ALWAYS uses real Telegram WebApp authentication
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
    // SECURITY: Only in DEV environment
    if (_isBrowserDebug) {
        // Log once per session to avoid spam
        if (!_didLogDebugPaymentsDisabled) {
            console.warn('[Auth] Using Debug Mode (DEV only) - payments disabled');
            _didLogDebugPaymentsDisabled = true;
        }
        return {
            'Content-Type': 'application/json',
            'X-Debug-Mode': 'true',
            'X-Debug-User-Id': String(user.id),
            'X-Telegram-Init-Data': initData,
            'X-Telegram-ID': String(user.id),
            'X-Telegram-First-Name': encodeURIComponent(user.first_name || ''),
            'X-Telegram-Username': encodeURIComponent(user.username || ''),
        };
    }

    // Обычный Telegram режим (production)
    return {
        'Content-Type': 'application/json',
        'X-Telegram-ID': String(user.id),
        'X-Telegram-First-Name': encodeURIComponent(user.first_name || ''),
        'X-Telegram-Username': encodeURIComponent(user.username || ''),
        'X-Telegram-Init-Data': initData,
    };
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
 * Применение safe-area insets из Telegram WebApp к CSS переменным
 */
export function applySafeAreaInsets(tg: any) {
    if (!tg?.safeAreaInset) return;

    const insetVars: Record<string, string> = {
        '--tg-safe-area-inset-top': `${tg.safeAreaInset.top}px`,
        '--tg-safe-area-inset-bottom': `${tg.safeAreaInset.bottom}px`,
        '--tg-safe-area-inset-left': `${tg.safeAreaInset.left}px`,
        '--tg-safe-area-inset-right': `${tg.safeAreaInset.right}px`,
    };

    Object.entries(insetVars).forEach(([key, value]) => {
        document.documentElement.style.setProperty(key, value);
    });

    console.log('[Telegram] Safe area insets applied:', {
        top: tg.safeAreaInset.top,
        bottom: tg.safeAreaInset.bottom,
        left: tg.safeAreaInset.left,
        right: tg.safeAreaInset.right,
    });
}

/**
 * Подписка на динамические изменения safe-area
 * Telegram может менять safe-area при изменениях viewport/панелей
 */
export function subscribeToSafeAreaChanges(tg: any) {
    if (!tg) return;

    // Telegram WebApp API v6.1+ поддерживает события safe area
    if (typeof tg.onEvent === 'function') {
        // safeAreaChanged - основное событие изменения safe area
        tg.onEvent('safeAreaChanged', () => {
            console.log('[Telegram] safeAreaChanged event fired');
            applySafeAreaInsets(tg);
        });

        // contentSafeAreaChanged - изменение content safe area
        tg.onEvent('contentSafeAreaChanged', () => {
            console.log('[Telegram] contentSafeAreaChanged event fired');
            applySafeAreaInsets(tg);
        });

        // viewportChanged - изменение viewport (может повлиять на safe area)
        tg.onEvent('viewportChanged', () => {
            console.log('[Telegram] viewportChanged event fired');
            applySafeAreaInsets(tg);
        });

        console.log('[Telegram] Subscribed to safe-area change events');
    } else {
        console.warn('[Telegram] Event subscription not supported (old API version)');
    }
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
