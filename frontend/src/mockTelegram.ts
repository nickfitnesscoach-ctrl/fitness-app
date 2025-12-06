
/**
 * Mock Telegram WebApp environment for local development
 */
export function mockTelegramEnv() {
    if (typeof window === 'undefined') return;

    // Force overwrite to ensure we have a valid mock
    console.log('[Mock] Initializing Telegram WebApp Mock (Force Overwrite)');

    (window as any).Telegram = {
        WebApp: {
            initData: "query_id=AAHdF6MUAAAAAN0XoxQrbkiV&user=%7B%22id%22%3A12345%2C%22first_name%22%3A%22DevUser%22%2C%22last_name%22%3A%22Local%22%2C%22username%22%3A%22devuser%22%2C%22language_code%22%3A%22en%22%2C%22is_premium%22%3Atrue%7D&auth_date=1701385000&hash=mocked_hash_for_dev",
            initDataUnsafe: {
                user: {
                    id: 12345,
                    first_name: "DevUser",
                    last_name: "Local",
                    username: "devuser",
                    language_code: "en",
                    is_premium: true
                },
                query_id: "AAHdF6MUAAAAAN0XoxQrbkiV",
                auth_date: 1701385000,
                hash: "mocked_hash_for_dev"
            },
            version: "7.0",
            platform: "tdesktop",
            colorScheme: "light",
            themeParams: {
                bg_color: "#ffffff",
                text_color: "#000000",
                hint_color: "#999999",
                link_color: "#2481cc",
                button_color: "#2481cc",
                button_text_color: "#ffffff",
                secondary_bg_color: "#f0f0f0"
            },
            isExpanded: true,
            viewportHeight: 800,
            viewportStableHeight: 800,
            headerColor: "#ffffff",
            backgroundColor: "#ffffff",
            isClosingConfirmationEnabled: false,
            BackButton: {
                isVisible: false,
                onClick: () => console.log('[Mock] BackButton.onClick'),
                offClick: () => console.log('[Mock] BackButton.offClick'),
                show: () => console.log('[Mock] BackButton.show'),
                hide: () => console.log('[Mock] BackButton.hide')
            },
            MainButton: {
                text: "CONTINUE",
                color: "#2481cc",
                textColor: "#ffffff",
                isVisible: false,
                isActive: true,
                isProgressVisible: false,
                setText: (text: string) => console.log(`[Mock] MainButton.setText: ${text}`),
                onClick: (_cb: Function) => console.log('[Mock] MainButton.onClick'),
                offClick: (_cb: Function) => console.log('[Mock] MainButton.offClick'),
                show: () => console.log('[Mock] MainButton.show'),
                hide: () => console.log('[Mock] MainButton.hide'),
                enable: () => console.log('[Mock] MainButton.enable'),
                disable: () => console.log('[Mock] MainButton.disable'),
                showProgress: () => console.log('[Mock] MainButton.showProgress'),
                hideProgress: () => console.log('[Mock] MainButton.hideProgress'),
                setParams: (params: any) => console.log('[Mock] MainButton.setParams', params),
            },
            HapticFeedback: {
                impactOccurred: (style: string) => console.log(`[Mock] Haptic.impact: ${style}`),
                notificationOccurred: (type: string) => console.log(`[Mock] Haptic.notification: ${type}`),
                selectionChanged: () => console.log('[Mock] Haptic.selectionChanged')
            },
            ready: () => console.log('[Mock] WebApp.ready()'),
            expand: () => console.log('[Mock] WebApp.expand()'),
            close: () => console.log('[Mock] WebApp.close()'),
            enableClosingConfirmation: () => console.log('[Mock] Enable closing confirmation'),
            disableClosingConfirmation: () => console.log('[Mock] Disable closing confirmation'),
            onEvent: (_eventType: string, _eventHandler: Function) => console.log(`[Mock] Registered event`),
            offEvent: (_eventType: string, _eventHandler: Function) => console.log(`[Mock] Unregistered event`),
            sendData: (data: any) => console.log(`[Mock] sendData`, data),
            openLink: (url: string) => window.open(url, '_blank'),
            openTelegramLink: (url: string) => window.open(url, '_blank'),
            openInvoice: (url: string) => console.log(`[Mock] openInvoice: ${url}`),
            showPopup: (params: any) => console.log(`[Mock] showPopup`, params),
            showAlert: (message: string) => alert(`[Mock Alert] ${message}`),
            showConfirm: (message: string) => confirm(`[Mock Confirm] ${message}`),
            CloudStorage: {
                getItem: (key: string, callback: Function) => {
                    console.log(`[Mock] CloudStorage.getItem: ${key}`);
                    callback(null, localStorage.getItem(`tg_cloud_${key}`));
                },
                setItem: (key: string, value: string, callback: Function) => {
                    console.log(`[Mock] CloudStorage.setItem: ${key}=${value}`);
                    localStorage.setItem(`tg_cloud_${key}`, value);
                    callback(null, true);
                },
                getItems: (_keys: string[], callback: Function) => callback(null, []),
                removeItem: (_key: string, callback: Function) => callback(null, true),
                removeItems: (_keys: string[], callback: Function) => callback(null, true),
                getKeys: (callback: Function) => callback(null, [])
            }
        }
    };
}
