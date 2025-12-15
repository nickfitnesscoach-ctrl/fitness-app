/// <reference types="vite/client" />

/**
 * Extend Vite's ImportMetaEnv interface with our custom variables
 * This provides autocomplete and type checking for import.meta.env
 */
interface ImportMetaEnv {
  // API Configuration
  readonly VITE_API_URL?: string;
  readonly VITE_TRAINER_PANEL_AUTH_URL?: string;

  // Telegram Configuration
  readonly VITE_TELEGRAM_BOT_NAME?: string;
  readonly VITE_TRAINER_INVITE_LINK?: string;

  // Development Flags
  readonly VITE_MOCK_TELEGRAM?: string;
  readonly VITE_SKIP_TG_AUTH?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
