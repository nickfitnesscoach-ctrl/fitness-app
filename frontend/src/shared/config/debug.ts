/**
 * Centralized Debug Configuration for EatFit24
 *
 * This module provides a single source of truth for debug mode detection.
 *
 * Debug mode behavior:
 * - DEV build (localhost): Always enabled, mock Telegram API active
 * - PROD build: Completely disabled, no mock, no banner, no URL override
 *
 * Security:
 * - In production, debug mode is ALWAYS disabled
 * - Mock Telegram API only initializes in DEV
 * - Debug banner only renders in DEV
 */

import { IS_DEV } from '../../config/env';

/**
 * Main debug flag - determines if debug mode is active
 *
 * TRUE when:
 * - Running in DEV environment (import.meta.env.DEV)
 *
 * FALSE when:
 * - Production build (ALWAYS)
 */
export const IS_DEBUG = IS_DEV;

/**
 * Debug user configuration for mock Telegram API
 * Used when IS_DEBUG is true
 */
export const DEBUG_USER = {
  id: 999999999,
  first_name: 'Debug',
  last_name: 'User',
  username: 'eatfit24_debug',
  language_code: 'ru',
  is_premium: false,
} as const;

/**
 * Debug token for backend authentication
 * Backend recognizes this via X-Debug-Mode header
 */
export const DEBUG_TOKEN = 'DEBUG_LOCAL_TOKEN';

/**
 * Check if mock Telegram API should be initialized
 */
export function shouldInitMockTelegram(): boolean {
  // Only init mock if debug is enabled AND no real Telegram WebApp exists
  return IS_DEBUG && !window.Telegram?.WebApp;
}

/**
 * Get debug info for logging
 */
export function getDebugInfo() {
  const searchParams = new URLSearchParams(window.location.search);
  return {
    isDebug: IS_DEBUG,
    isDev: IS_DEV,
    hasDebugParam: searchParams.has("debug"),
    hasTelegram: Boolean(window.Telegram?.WebApp),
    shouldMock: shouldInitMockTelegram(),
  };
}
