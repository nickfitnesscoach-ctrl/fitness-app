/**
 * Unified React hook for Telegram WebApp integration.
 *
 * Replaces all ad-hoc checks of window.Telegram.WebApp in components.
 * Guarantees correct WebApp detection and graceful degradation.
 */

import { useState, useEffect } from 'react';
import {
    initTelegramWebApp,
    getTelegramWebApp,
    isDebugModeEnabled,
    type TelegramUserInfo
} from '../lib/telegram';

export type TelegramPlatform = 'ios' | 'android' | 'tdesktop' | 'macos' | 'web' | 'unknown';

export interface UseTelegramWebAppResult {
    /** WebApp is ready to use */
    isReady: boolean;

    /** Application is running inside Telegram WebApp */
    isTelegramWebApp: boolean;

    /** Browser Debug Mode is active (testing in regular browser) */
    isBrowserDebug: boolean;

    /** Telegram user ID (if available) */
    telegramUserId: number | null;

    /** Telegram user data (if available) */
    telegramUser: TelegramUserInfo | null;

    /** Telegram WebApp instance (for direct access) */
    webApp: any | null;

    /** Платформа: ios, android, tdesktop, macos, web */
    platform: TelegramPlatform;

    /** Запущено на мобильном устройстве (iOS или Android) */
    isMobile: boolean;

    /** Запущено на десктопе (tdesktop, macos, web) */
    isDesktop: boolean;
}

/**
 * Hook for working with Telegram WebApp.
 *
 * @example
 * ```tsx
 * const { isReady, isTelegramWebApp, telegramUserId } = useTelegramWebApp();
 *
 * if (!isReady) {
 *     return <Skeleton />;  // Loading
 * }
 *
 * if (!isTelegramWebApp) {
 *     return <Banner>Open via bot</Banner>;
 * }
 *
 * // Work with the app
 * ```
 */
export function useTelegramWebApp(): UseTelegramWebAppResult {
    const [isReady, setIsReady] = useState(false);
    const [isTelegramWebApp, setIsTelegramWebApp] = useState(false);
    const [isBrowserDebug, setIsBrowserDebug] = useState(false);
    const [telegramUserId, setTelegramUserId] = useState<number | null>(null);
    const [telegramUser, setTelegramUser] = useState<TelegramUserInfo | null>(null);
    const [webApp, setWebApp] = useState<any | null>(null);
    const [platform, setPlatform] = useState<TelegramPlatform>('unknown');

    useEffect(() => {
        const initializeWebApp = async () => {
            // Use centralized initialization from telegram module
            const authData = await initTelegramWebApp();

            // Check if we're in debug mode
            const debugMode = isDebugModeEnabled();
            setIsBrowserDebug(debugMode);

            // Get WebApp instance for platform detection
            const tg = getTelegramWebApp();

            if (tg) {
                setWebApp(tg);
                // Определяем платформу
                const tgPlatform = (tg.platform || 'unknown').toLowerCase() as TelegramPlatform;
                setPlatform(tgPlatform);
            } else if (debugMode) {
                // Debug mode without Telegram
                setPlatform('web');
            }

            if (authData) {
                // Successfully initialized (either real Telegram or debug mode)
                setIsTelegramWebApp(!debugMode); // Only true for real Telegram
                setTelegramUserId(Number(authData.user.id));
                setTelegramUser(authData.user);
            } else {
                // Not in Telegram and not in debug mode
                setIsTelegramWebApp(false);
            }

            setIsReady(true);
        };

        initializeWebApp();
    }, []);

    // Вычисляем isMobile/isDesktop на основе платформы
    const isMobile = platform === 'ios' || platform === 'android';
    const isDesktop = platform === 'tdesktop' || platform === 'macos' || platform === 'web';

    return {
        isReady,
        isTelegramWebApp,
        isBrowserDebug,
        telegramUserId,
        telegramUser,
        webApp,
        platform,
        isMobile,
        isDesktop,
    };
}
