/**
 * Unified React hook for Telegram WebApp integration.
 *
 * Replaces all ad-hoc checks of window.Telegram.WebApp in components.
 * Guarantees correct WebApp detection and graceful degradation.
 */

import { useState, useEffect } from 'react';
import { getTelegramWebApp, type TelegramUserInfo } from '../lib/telegram';

export interface UseTelegramWebAppResult {
    /** WebApp is ready to use */
    isReady: boolean;

    /** Application is running inside Telegram WebApp */
    isTelegramWebApp: boolean;

    /** Telegram user ID (if available) */
    telegramUserId: number | null;

    /** Telegram user data (if available) */
    telegramUser: TelegramUserInfo | null;

    /** Telegram WebApp instance (for direct access) */
    webApp: any | null;
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
    const [telegramUserId, setTelegramUserId] = useState<number | null>(null);
    const [telegramUser, setTelegramUser] = useState<TelegramUserInfo | null>(null);
    const [webApp, setWebApp] = useState<any | null>(null);

    useEffect(() => {
        // Give time for window.Telegram to load (CDN script)
        const checkWebApp = () => {
            const tg = getTelegramWebApp();

            if (!tg) {
                // Telegram WebApp not found
                setIsTelegramWebApp(false);
                setIsReady(true);
                return;
            }

            setWebApp(tg);

            // Check for initData (main indicator)
            if (!tg.initData) {
                // WebApp exists but initData is empty (opened in browser)
                setIsTelegramWebApp(false);
                setIsReady(true);
                return;
            }

            // WebApp is available and initData exists
            try {
                tg.ready?.();
                tg.expand?.();
            } catch (e) {
                console.warn('[useTelegramWebApp] Error calling ready():', e);
            }

            setIsTelegramWebApp(true);

            // Extract user data
            const initDataUnsafe = tg.initDataUnsafe;
            if (initDataUnsafe?.user?.id) {
                const user = initDataUnsafe.user as TelegramUserInfo;
                setTelegramUserId(Number(user.id));
                setTelegramUser(user);
            }

            setIsReady(true);
        };

        // Run check with a small delay (for CDN loading)
        const timeoutId = setTimeout(checkWebApp, 100);

        return () => clearTimeout(timeoutId);
    }, []);

    return {
        isReady,
        isTelegramWebApp,
        telegramUserId,
        telegramUser,
        webApp,
    };
}
