/**
 * Mock Telegram WebApp API for Debug Mode
 *
 * Provides a complete mock implementation of Telegram WebApp API
 * for local development and debug testing.
 *
 * This mock is only initialized when:
 * - Debug mode is enabled (DEV or ?debug=1)
 * - No real Telegram WebApp is available
 *
 * Security: This code never runs in production unless ?debug=1 is explicitly set
 */

import { DEBUG_USER } from '../config/debug';

/**
 * Initialize mock Telegram WebApp environment
 *
 * This creates a complete mock of window.Telegram.WebApp with all required methods.
 * The mock uses DEBUG_USER configuration for user data.
 */
export function setupMockTelegram(): void {
  if (typeof window === 'undefined') {
    console.warn('[MockTelegram] Cannot setup - window is undefined');
    return;
  }

  // Check if already initialized
  if (window.Telegram?.WebApp) {
    console.log('[MockTelegram] Telegram WebApp already exists, skipping mock');
    return;
  }

  console.log('[MockTelegram] Initializing mock Telegram WebApp environment');

  // Build initData string with debug user
  const initDataString = buildMockInitData(DEBUG_USER);

  // Create mock WebApp object
  (window as any).Telegram = {
    WebApp: {
      // Init data
      initData: initDataString,
      initDataUnsafe: {
        user: DEBUG_USER,
        query_id: 'AAHdF6MUAAAAAN0XoxQrbkiV',
        auth_date: Math.floor(Date.now() / 1000),
        hash: 'mocked_hash_for_debug',
      },

      // Environment info
      version: '7.0',
      platform: 'tdesktop',
      colorScheme: 'light',
      isExpanded: true,
      viewportHeight: 800,
      viewportStableHeight: 800,
      headerColor: '#ffffff',
      backgroundColor: '#ffffff',
      isClosingConfirmationEnabled: false,

      // Theme params
      themeParams: {
        bg_color: '#ffffff',
        text_color: '#000000',
        hint_color: '#999999',
        link_color: '#2481cc',
        button_color: '#2481cc',
        button_text_color: '#ffffff',
        secondary_bg_color: '#f0f0f0',
      },

      // Back Button
      BackButton: {
        isVisible: false,
        onClick: (callback: Function) => {
          console.log('[MockTelegram] BackButton.onClick registered');
          return callback;
        },
        offClick: (callback: Function) => {
          console.log('[MockTelegram] BackButton.offClick', callback);
        },
        show: () => {
          console.log('[MockTelegram] BackButton.show');
        },
        hide: () => {
          console.log('[MockTelegram] BackButton.hide');
        },
      },

      // Main Button
      MainButton: {
        text: 'CONTINUE',
        color: '#2481cc',
        textColor: '#ffffff',
        isVisible: false,
        isActive: true,
        isProgressVisible: false,
        setText: (text: string) => {
          console.log(`[MockTelegram] MainButton.setText: ${text}`);
        },
        onClick: (callback: Function) => {
          console.log('[MockTelegram] MainButton.onClick registered');
          return callback;
        },
        offClick: (callback: Function) => {
          console.log('[MockTelegram] MainButton.offClick', callback);
        },
        show: () => {
          console.log('[MockTelegram] MainButton.show');
        },
        hide: () => {
          console.log('[MockTelegram] MainButton.hide');
        },
        enable: () => {
          console.log('[MockTelegram] MainButton.enable');
        },
        disable: () => {
          console.log('[MockTelegram] MainButton.disable');
        },
        showProgress: () => {
          console.log('[MockTelegram] MainButton.showProgress');
        },
        hideProgress: () => {
          console.log('[MockTelegram] MainButton.hideProgress');
        },
        setParams: (params: any) => {
          console.log('[MockTelegram] MainButton.setParams', params);
        },
      },

      // Haptic Feedback
      HapticFeedback: {
        impactOccurred: (style: string) => {
          console.log(`[MockTelegram] Haptic.impact: ${style}`);
        },
        notificationOccurred: (type: string) => {
          console.log(`[MockTelegram] Haptic.notification: ${type}`);
        },
        selectionChanged: () => {
          console.log('[MockTelegram] Haptic.selectionChanged');
        },
      },

      // Core methods
      ready: () => {
        console.log('[MockTelegram] WebApp.ready()');
      },
      expand: () => {
        console.log('[MockTelegram] WebApp.expand()');
      },
      close: () => {
        console.log('[MockTelegram] WebApp.close()');
      },
      enableClosingConfirmation: () => {
        console.log('[MockTelegram] Enable closing confirmation');
      },
      disableClosingConfirmation: () => {
        console.log('[MockTelegram] Disable closing confirmation');
      },

      // Events
      onEvent: (eventType: string, eventHandler: Function) => {
        console.log(`[MockTelegram] Registered event: ${eventType}`);
        return eventHandler;
      },
      offEvent: (eventType: string, eventHandler: Function) => {
        console.log(`[MockTelegram] Unregistered event: ${eventType}`, eventHandler);
      },

      // Data & Links
      sendData: (data: any) => {
        console.log('[MockTelegram] sendData', data);
      },
      openLink: (url: string) => {
        console.log(`[MockTelegram] openLink: ${url}`);
        window.open(url, '_blank');
      },
      openTelegramLink: (url: string) => {
        console.log(`[MockTelegram] openTelegramLink: ${url}`);
        window.open(url, '_blank');
      },
      openInvoice: (url: string) => {
        console.log(`[MockTelegram] openInvoice: ${url}`);
      },

      // Popups
      showPopup: (params: any) => {
        console.log('[MockTelegram] showPopup', params);
        if (params.message) {
          alert(`[Mock Popup] ${params.message}`);
        }
      },
      showAlert: (message: string) => {
        console.log(`[MockTelegram] showAlert: ${message}`);
        alert(`[Mock Alert] ${message}`);
      },
      showConfirm: (message: string, callback?: (confirmed: boolean) => void) => {
        console.log(`[MockTelegram] showConfirm: ${message}`);
        const result = confirm(`[Mock Confirm] ${message}`);
        if (callback) callback(result);
      },

      // Cloud Storage
      CloudStorage: {
        getItem: (key: string, callback: (error: Error | null, value: string | null) => void) => {
          console.log(`[MockTelegram] CloudStorage.getItem: ${key}`);
          const value = localStorage.getItem(`tg_cloud_${key}`);
          setTimeout(() => callback(null, value), 10);
        },
        setItem: (key: string, value: string, callback: (error: Error | null, success: boolean) => void) => {
          console.log(`[MockTelegram] CloudStorage.setItem: ${key}=${value}`);
          localStorage.setItem(`tg_cloud_${key}`, value);
          setTimeout(() => callback(null, true), 10);
        },
        removeItem: (key: string, callback: (error: Error | null, success: boolean) => void) => {
          console.log(`[MockTelegram] CloudStorage.removeItem: ${key}`);
          localStorage.removeItem(`tg_cloud_${key}`);
          setTimeout(() => callback(null, true), 10);
        },
        getItems: (keys: string[], callback: (error: Error | null, values: string[]) => void) => {
          console.log('[MockTelegram] CloudStorage.getItems', keys);
          setTimeout(() => callback(null, []), 10);
        },
        removeItems: (keys: string[], callback: (error: Error | null, success: boolean) => void) => {
          console.log('[MockTelegram] CloudStorage.removeItems', keys);
          setTimeout(() => callback(null, true), 10);
        },
        getKeys: (callback: (error: Error | null, keys: string[]) => void) => {
          console.log('[MockTelegram] CloudStorage.getKeys');
          setTimeout(() => callback(null, []), 10);
        },
      },
    },
  };

  console.log('[MockTelegram] Mock initialized successfully', {
    userId: DEBUG_USER.id,
    username: DEBUG_USER.username,
  });
}

/**
 * Build mock initData string
 * Mimics the format of real Telegram WebApp initData
 */
function buildMockInitData(user: typeof DEBUG_USER): string {
  const userJson = JSON.stringify({
    id: user.id,
    first_name: user.first_name,
    last_name: user.last_name,
    username: user.username,
    language_code: user.language_code,
    is_premium: user.is_premium,
  });

  const authDate = Math.floor(Date.now() / 1000);

  return `query_id=AAHdF6MUAAAAAN0XoxQrbkiV&user=${encodeURIComponent(userJson)}&auth_date=${authDate}&hash=mocked_hash_for_debug`;
}

/**
 * Clean up mock Telegram (for testing)
 */
export function cleanupMockTelegram(): void {
  if (typeof window !== 'undefined') {
    delete (window as any).Telegram;
    console.log('[MockTelegram] Mock cleaned up');
  }
}
