import { useMemo, useRef, useState } from 'react';
import { useBilling } from '../../../contexts/BillingContext';
import { useAuth } from '../../../contexts/AuthContext';
import { api } from '../../../services/api';
import { formatShortDate } from '../utils/date';
import { showToast } from '../utils/notify';
import type { SubscriptionDetails } from '../../../types/billing';

interface UseSubscriptionDetailsResult {
    subscription: SubscriptionDetails | null;
    isPro: boolean;
    expiresAtFormatted: string;
    autoRenewEnabled: boolean;
    autoRenewAvailable: boolean;
    hasCard: boolean;
    cardInfoLabel: string;

    isAdmin: boolean;
    testLivePaymentAvailable: boolean;
    togglingAutoRenew: boolean;
    creatingTestPayment: boolean;

    handleToggleAutoRenew: () => Promise<void>;
    handlePaymentMethodClick: () => Promise<void>;
    handleCreateTestPayment: () => Promise<void>;
}

export const useSubscriptionDetails = (): UseSubscriptionDetailsResult => {
    const billing = useBilling();
    const auth = useAuth();

    const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);
    const [creatingTestPayment, setCreatingTestPayment] = useState(false);

    const inFlightRef = useRef<Set<string>>(new Set());

    const subscription = billing.subscription;

    const isPro = subscription?.plan === 'pro';
    const expiresAt = subscription?.expires_at ?? null;
    const expiresAtFormatted = formatShortDate(expiresAt);

    const autoRenewEnabled = subscription?.autorenew_enabled ?? false;
    const autoRenewAvailable = subscription?.autorenew_available ?? false;

    const paymentMethod = subscription?.payment_method;
    const hasCard = paymentMethod?.is_attached ?? false;

    const isAdmin = auth.isAdmin ?? false;
    const testLivePaymentAvailable = billing.billingMe?.test_live_payment_available ?? false;

    const cardInfoLabel = useMemo(() => {
        if (!hasCard || !paymentMethod) return 'Карта не привязана';
        const mask = paymentMethod.card_mask || '••••';
        const brand = paymentMethod.card_brand || 'Card';
        return `${mask} · ${brand}`;
    }, [hasCard, paymentMethod]);

    const handleToggleAutoRenew = async (): Promise<void> => {
        const lockKey = 'autorenew:toggle';
        if (togglingAutoRenew || inFlightRef.current.has(lockKey)) return;

        if (!autoRenewAvailable) {
            showToast('Автопродление недоступно — привяжите карту');
            return;
        }

        inFlightRef.current.add(lockKey);
        setTogglingAutoRenew(true);

        try {
            await billing.setAutoRenew(!autoRenewEnabled);
            showToast(autoRenewEnabled ? 'Автопродление отключено' : 'Автопродление включено');
        } catch (error) {
            console.error('[billing] setAutoRenew error:', error);
            const message = error instanceof Error ? error.message : 'Не удалось изменить настройки';
            showToast(message);
        } finally {
            setTogglingAutoRenew(false);
            inFlightRef.current.delete(lockKey);
        }
    };

    const handlePaymentMethodClick = async (): Promise<void> => {
        const lockKey = 'payment-method:click';
        if (inFlightRef.current.has(lockKey)) return;

        // пока не поддерживаем смену карты — только привязка
        if (hasCard) {
            showToast('Смена карты будет доступна позже');
            return;
        }

        inFlightRef.current.add(lockKey);
        try {
            await billing.addPaymentMethod();
        } catch (error) {
            console.error('[billing] addPaymentMethod error:', error);
            let errorMessage = 'Ошибка при запуске привязки карты';
            if (error instanceof Error && error.message) {
                try {
                    const data = JSON.parse(error.message);
                    errorMessage = data?.message || errorMessage;
                } catch {
                    errorMessage = error.message || errorMessage;
                }
            }
            showToast(errorMessage);
        } finally {
            inFlightRef.current.delete(lockKey);
        }
    };

    const handleCreateTestPayment = async (): Promise<void> => {
        const lockKey = 'admin:test-payment';
        if (creatingTestPayment || inFlightRef.current.has(lockKey)) return;

        // defense-in-depth (не только UI)
        if (!isAdmin || !testLivePaymentAvailable) {
            showToast('Недостаточно прав');
            return;
        }

        inFlightRef.current.add(lockKey);
        setCreatingTestPayment(true);

        try {
            // API может редиректить внутри себя; если вернёт URL — откроем
            const res: any = await api.createTestLivePayment();
            const url = res?.confirmation_url;

            if (typeof url === 'string' && url.length > 0) {
                const isTMA = typeof window !== 'undefined' && Boolean(window.Telegram?.WebApp?.initData);
                if (isTMA && window.Telegram?.WebApp?.openLink) {
                    window.Telegram.WebApp.openLink(url);
                } else {
                    window.location.href = url;
                }
            }
        } catch (error) {
            console.error('[billing] createTestLivePayment error:', error);
            const message = error instanceof Error ? error.message : 'Ошибка при создании тестового платежа';
            showToast(message);
        } finally {
            setCreatingTestPayment(false);
            inFlightRef.current.delete(lockKey);
        }
    };

    return {
        subscription,
        isPro,
        expiresAtFormatted,
        autoRenewEnabled,
        autoRenewAvailable,
        hasCard,
        cardInfoLabel,

        isAdmin,
        testLivePaymentAvailable,
        togglingAutoRenew,
        creatingTestPayment,

        handleToggleAutoRenew,
        handlePaymentMethodClick,
        handleCreateTestPayment,
    };
};
