/**
 * Debug Mode Banner Component
 *
 * Displays a prominent warning banner when debug mode is active.
 * Only renders when IS_DEBUG is true (DEV only).
 *
 * This banner:
 * - Appears at the top of the app in DEV environment only
 * - Shows debug user information
 * - NEVER renders in production
 */

import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { IS_DEBUG } from '../../shared/config/debug';

const DebugBanner: React.FC = () => {
  const { telegramUser } = useAuth();

  // Only render in DEV mode (never in production)
  if (!IS_DEBUG) {
    return null;
  }

  return (
    <div className="fixed top-0 left-0 right-0 bg-red-600 text-white px-4 py-2 z-50 shadow-lg">
      <div className="max-w-7xl mx-auto flex items-center justify-center gap-2 text-sm font-medium">
        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
        <span>
          DEBUG MODE • USER: {telegramUser?.username || 'debug'} • ID: {telegramUser?.id}
        </span>
      </div>
    </div>
  );
};

export default DebugBanner;
