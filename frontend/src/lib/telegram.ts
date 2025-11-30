/**
 * Централизованный модуль для работы с Telegram WebApp
 *
 * Этот модуль обеспечивает:
 * - Единую точку инициализации Telegram WebApp
 * - Формирование auth headers для API запросов
 * - DEV режим для локальной разработки
 */

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
// Internal State
// ============================================================
// ============================================================
// Internal State
// ============================================================

let _telegramAuthData: TelegramAuthData | null = null;
let _initPromise: Promise<TelegramAuthData | null> | null = null;

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
 * @throws Error если Telegram не инициализирован
 */
export function buildTelegramHeaders(): HeadersInit {
    if (!_telegramAuthData) {
        console.error('[Telegram] Headers requested but not initialized!');
        console.error('[Telegram] Stack trace:', new Error().stack);
        // Возвращаем пустые headers вместо throw - для graceful degradation
        return {
            'Content-Type': 'application/json',
        };
    }

    const { initData, user } = _telegramAuthData;

    console.log('[Telegram] Building headers with user ID:', user.id);

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
export function getTelegramInitData(devMode = false): string | null {
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
    };
}
