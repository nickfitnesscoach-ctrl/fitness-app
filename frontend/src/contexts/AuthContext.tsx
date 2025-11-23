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
    getTelegramAuthData,
    isTelegramInitialized,
    type TelegramUserInfo,
} from '../lib/telegram';

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
}

interface AuthContextType {
    user: User | null;
    telegramUser: TelegramUserInfo | null;
    loading: boolean;
    error: string | null;
    isInitialized: boolean;
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

    /**
     * Инициализация и аутентификация
     */
    const authenticate = async () => {
        try {
            setLoading(true);
            setError(null);

            // Шаг 1: Инициализация Telegram WebApp
            console.log('[Auth] Initializing Telegram WebApp...');
            const authData = await initTelegramWebApp();

            if (!authData) {
                console.warn('[Auth] Telegram WebApp not available');
                setError('Telegram WebApp не инициализирован. Откройте приложение через Telegram.');
                setLoading(false);
                return;
            }

            setTelegramUser(authData.user);
            setIsInitialized(true);
            console.log('[Auth] Telegram initialized:', authData.user.id);

            // Шаг 2: Аутентификация на backend (для получения user info)
            // NOTE: JWT токены из response игнорируются, используем Header auth
            try {
                const response = await api.authenticate(authData.initData);
                console.log('[Auth] Backend auth response:', response);

                if (response.user) {
                    const userData = response.user;
                    const role = userData.is_client ? 'client' : 'trainer';
                    setUser({ ...userData, role });
                }
            } catch (authError) {
                // Backend auth failed, но Telegram init успешен
                // Можно продолжить работу с ограниченной функциональностью
                console.error('[Auth] Backend auth failed:', authError);
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
