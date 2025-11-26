/**
 * BillingContext - Глобальное состояние подписки и лимитов
 *
 * Предоставляет:
 * - Информацию о текущем тарифе (FREE/MONTHLY/YEARLY)
 * - Дневные лимиты фото и использование
 * - Методы обновления состояния
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { api } from '../services/api';
import { BillingState, BillingMe } from '../types/billing';
import { useAuth } from './AuthContext';

interface BillingContextType extends BillingState {
    refresh: () => Promise<void>;
    isLimitReached: boolean;
    isPro: boolean;
}

const BillingContext = createContext<BillingContextType | undefined>(undefined);

export const useBilling = () => {
    const context = useContext(BillingContext);
    if (!context) {
        console.error('[useBilling] Error: Context is undefined. Check if component is wrapped in BillingProvider.');
        throw new Error('useBilling must be used within BillingProvider');
    }
    return context;
};

interface BillingProviderProps {
    children: React.ReactNode;
}

export const BillingProvider: React.FC<BillingProviderProps> = ({ children }) => {
    const auth = useAuth();
    const mounted = useRef(true);

    const [state, setState] = useState<BillingState>({
        data: null,
        loading: true,
        error: null,
    });

    // Cleanup on unmount
    useEffect(() => {
        mounted.current = true;
        return () => {
            mounted.current = false;
        };
    }, []);

    /**
     * Обновить данные подписки с сервера
     */
    const refresh = useCallback(async () => {
        // Не загружаем, пока не авторизовались
        if (!auth.isInitialized) {
            console.log('[BillingProvider] Waiting for auth initialization...');
            return;
        }

        try {
            if (mounted.current) {
                setState(prev => ({ ...prev, loading: true, error: null }));
            }

            const data = await api.getBillingMe();

            if (mounted.current) {
                setState({
                    data,
                    loading: false,
                    error: null,
                });
            }
        } catch (error) {
            console.error('[BillingProvider] Failed to fetch billing data:', error);

            // Fallback: устанавливаем FREE план с лимитом 3 при ошибке
            if (mounted.current) {
                setState({
                    loading: false,
                    error: error instanceof Error ? error.message : 'Failed to load billing data',
                    data: {
                        plan_code: 'FREE',
                        plan_name: 'Бесплатный',
                        expires_at: null,
                        is_active: true,
                        daily_photo_limit: 3,
                        used_today: 0,
                        remaining_today: 3,
                    },
                });
            }
        }
    }, [auth.isInitialized]);

    // Загрузка при инициализации авторизации
    useEffect(() => {
        if (auth.isInitialized) {
            console.log('[BillingProvider] Auth initialized, fetching billing data...');
            refresh();
        } else {
            console.log('[BillingProvider] Auth not yet initialized');
        }
    }, [auth.isInitialized, refresh]);

    // Вычисляемые значения
    const isLimitReached = state.data
        ? state.data.daily_photo_limit !== null && state.data.used_today >= state.data.daily_photo_limit
        : false;

    const isPro = state.data ? ['MONTHLY', 'YEARLY'].includes(state.data.plan_code) : false;

    const value = useMemo<BillingContextType>(() => ({
        ...state,
        refresh,
        isLimitReached,
        isPro,
    }), [state, refresh, isLimitReached, isPro]);

    // Debug mount
    useEffect(() => {
        console.log('[BillingProvider] Mounted');
    }, []);

    return <BillingContext.Provider value={value}>{children}</BillingContext.Provider>;
};
