/**
 * AuthContext для FoodMind WebApp
 *
 * Использует Telegram WebApp для аутентификации.
 * JWT токены НЕ используются - все запросы идут через Header auth.
 */

import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';
import {
    initTelegramWebApp,
    type TelegramUserInfo,
} from '../lib/telegram';
import { IS_DEBUG } from '../shared/config/debug';

// ============================================================
// Types
// ============================================================

interface User {
    id: number;
    username: string;
    telegram_id: number;
    first_name: string;
    last_name?: string;
    completed_ai_test: boolean;
    is_client?: boolean;
    role?: 'trainer' | 'client';
    is_admin?: boolean;
}

interface AuthContextType {
    user: User | null;
    telegramUser: TelegramUserInfo | null;
    loading: boolean;
    error: string | null;
    isInitialized: boolean;
    isAdmin: boolean;
    isBrowserDebug: boolean;
    authenticate: () => Promise<void>;
    logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

// ============================================================
// Provider
// ============================================================

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const [user, setUser] = useState<User | null>(null);
    const [telegramUser, setTelegramUser] = useState<TelegramUserInfo | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isInitialized, setIsInitialized] = useState(false);
    const [isBrowserDebug, setIsBrowserDebug] = useState(false);

    /**
     * Инициализация и аутентификация
     */
    const authenticate = async () => {
        try {
            setLoading(true);
            setError(null);

            // Check if debug mode is active
            if (IS_DEBUG) {
                console.log('[Auth] Debug Mode enabled');
                setIsBrowserDebug(true);
            }

            // Шаг 1: Инициализация Telegram WebApp (или Debug Mode)
            console.log('[Auth] Initializing Telegram WebApp...');
            const authData = await initTelegramWebApp();

            if (!authData) {
                console.warn('[Auth] Telegram WebApp not available');
                if (!IS_DEBUG) {
                    setError('Telegram WebApp не инициализирован. Откройте приложение через Telegram.');
                }
                setLoading(false);
                return;
            }

            setTelegramUser(authData.user);
            setIsInitialized(true);
            console.log('[Auth] Telegram initialized:', authData.user.id);

            // Шаг 2: Аутентификация на backend (для получения user info)
            // NOTE: JWT токены из response игнорируются, используем Header auth
            // В Browser Debug Mode backend должен распознать X-Debug-Mode заголовок
            try {
                const response = await api.authenticate(authData.initData);
                console.log('[Auth] Backend auth response:', response);

                if (response.user) {
                    const userData = response.user;
                    const role = userData.is_client ? 'client' : 'trainer';
                    // is_admin приходит из backend в response
                    setUser({
                        ...userData,
                        role,
                        is_admin: response.is_admin || false
                    });
                }
            } catch (authError) {
                // Backend auth failed, но Telegram init успешен
                // В Debug Mode это нормально - можем работать без backend
                console.error('[Auth] Backend auth failed:', authError);
                if (IS_DEBUG) {
                    console.log('[Auth] Debug Mode: continuing without backend auth');
                }
                // Не устанавливаем error - пользователь может работать
            }
        } catch (err) {
            console.error('[Auth] Initialization error:', err);
            setError(err instanceof Error ? err.message : 'Ошибка инициализации');
        } finally {
            setLoading(false);
        }
    };

    const logout = () => {
        setUser(null);
        // Telegram user остаётся - это данные из WebApp
    };

    // Автоматическая инициализация при монтировании
    useEffect(() => {
        authenticate();
    }, []);

    return (
        <AuthContext.Provider
            value={{
                user,
                telegramUser,
                loading,
                error,
                isInitialized,
                isAdmin: user?.is_admin || false,
                isBrowserDebug,
                authenticate,
                logout,
            }}
        >
            {children}
        </AuthContext.Provider>
    );
};

// ============================================================
// Hook
// ============================================================

export const useAuth = () => {
    const context = useContext(AuthContext);
    if (!context) {
        throw new Error('useAuth must be used within AuthProvider');
    }
    return context;
};
