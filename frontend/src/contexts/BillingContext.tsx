/**
 * BillingContext - Глобальное состояние подписки и лимитов
 *
 * Предоставляет:
 * - Информацию о текущем тарифе (FREE/PRO_MONTHLY/PRO_YEARLY)
 * - Дневные лимиты фото и использование
 * - Методы обновления состояния
 */

import React, { createContext, useContext, useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { api } from '../services/api';
import { SubscriptionDetails, BillingMe } from '../types/billing';
import { useAuth } from './AuthContext';

interface BillingContextType {
    // Subscription details
    subscription: SubscriptionDetails | null;

    // Legacy /billing/me/ data (для обратной совместимости)
    billingMe: BillingMe | null;

    // States
    loading: boolean;
    error: string | null;

    // Methods
    refresh: () => Promise<void>;
    toggleAutoRenew: (enable: boolean) => Promise<void>; // Kept for compatibility, redirects to setAutoRenew
    setAutoRenew: (enabled: boolean) => Promise<void>;
    addPaymentMethod: () => Promise<void>;

    // Computed properties
    isPro: boolean;
    isLimitReached: boolean;

    // Legacy properties for compatibility
    data: BillingMe | null;
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

export const BillingProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const auth = useAuth(); // Get full auth context for initialization check
    const mounted = useRef(true);

    const [state, setState] = useState<{
        subscription: SubscriptionDetails | null;
        billingMe: BillingMe | null;
        loading: boolean;
        error: string | null;
    }>({
        subscription: null,
        billingMe: null,
        loading: true,
        error: null,
    });

    useEffect(() => {
        mounted.current = true;
        return () => {
            mounted.current = false;
        };
    }, []);

    const refresh = useCallback(async () => {
        if (!auth.isInitialized) {
            console.log('[BillingProvider] Waiting for auth initialization...');
            return;
        }

        try {
            if (mounted.current) {
                setState(prev => ({ ...prev, loading: true, error: null }));
            }

            // Загружаем ОБА эндпоинта параллельно
            const [subscriptionData, billingMeData] = await Promise.all([
                api.getSubscriptionDetails(),
                api.getBillingMe(), // Для лимитов фото
            ]);

            if (mounted.current) {
                setState({
                    subscription: subscriptionData,
                    billingMe: billingMeData,
                    loading: false,
                    error: null,
                });
            }
        } catch (error) {
            console.error('[BillingProvider] Failed to fetch billing data:', error);

            if (mounted.current) {
                setState(prev => ({
                    ...prev,
                    loading: false,
                    error: error instanceof Error ? error.message : 'Failed to load billing data',
                    // Fallback data is harder to mock with two sources, keeping nulls or partials might be better
                    // But for safety, let's leave them as is or provide basic fallbacks if critical
                }));
            }
        }
    }, [auth.isInitialized]);

    // Initial load
    useEffect(() => {
        if (auth.isInitialized) {
            refresh();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [auth.isInitialized]); // Only trigger on auth initialization, not on refresh change

    /**
     * Toggle auto-renew
     */
    const setAutoRenew = useCallback(async (enabled: boolean) => {
        try {
            const updatedSubscription = await api.setAutoRenew(enabled);

            if (mounted.current) {
                setState(prev => ({
                    ...prev,
                    subscription: updatedSubscription,
                }));
            }
        } catch (error) {
            console.error('[BillingContext] Failed to toggle auto-renew:', error);
            throw error;
        }
    }, []);

    const toggleAutoRenew = useCallback(async (enable: boolean) => {
        return setAutoRenew(enable);
    }, [setAutoRenew]);

    const addPaymentMethod = useCallback(async () => {
        try {
            await api.bindCard();
            // После привязки карты обновляем данные подписки
            await refresh();
        } catch (error) {
            console.error('[BillingContext] Failed to bind card:', error);
            throw error;
        }
    }, [refresh]);

    const isPro = useMemo(() => {
        return state.subscription?.plan === 'pro' && state.subscription?.is_active;
    }, [state.subscription]);

    const isLimitReached = useMemo(() => {
        const remaining = state.billingMe?.remaining_today;
        return remaining !== null && remaining !== undefined && remaining <= 0;
    }, [state.billingMe]);

    const value = useMemo(() => ({
        ...state,
        refresh,
        toggleAutoRenew,
        setAutoRenew,
        addPaymentMethod,
        isPro: !!isPro,
        isLimitReached: !!isLimitReached,
        data: state.billingMe // Alias for legacy support
    }), [state, refresh, toggleAutoRenew, setAutoRenew, addPaymentMethod, isPro, isLimitReached]);

    return (
        <BillingContext.Provider value={value}>
            {children}
        </BillingContext.Provider>
    );
};
