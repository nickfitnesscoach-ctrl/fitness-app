import { useCallback, useRef, useState } from 'react';
import type { SubscriptionPlan } from '../../../types/billing';
import type { PlanCode } from '../utils/types';
import { api } from '../../../services/api';
import { useBilling } from '../../../contexts/BillingContext';
import { showToast } from '../utils/notify';
import { setPollingFlagForPayment } from './usePaymentPolling';

interface UseSubscriptionActionsParams {
    plans: SubscriptionPlan[];
    isBrowserDebug: boolean;
    webAppBrowserDebug: boolean;
}

interface UseSubscriptionActionsResult {
    loadingPlanCode: PlanCode | null;
    togglingAutoRenew: boolean;
    handleSelectPlan: (planCode: PlanCode) => Promise<void>;
    handleToggleAutoRenew: () => Promise<void>;
    handleAddCard: () => Promise<void>;
}

const PAYMENT_URL_ALLOWLIST = [
    // YooKassa / YooMoney commonly used hosts (keep tight; extend only if реально нужно)
    'yookassa.ru',
    'checkout.yookassa.ru',
    'yoomoney.ru',
];

function isAllowedPaymentUrl(rawUrl: string): boolean {
    try {
        const u = new URL(rawUrl);
        if (u.protocol !== 'https:') return false;

        const host = u.hostname.toLowerCase();
        return PAYMENT_URL_ALLOWLIST.some((allowed) => host === allowed || host.endsWith(`.${allowed}`));
    } catch {
        return false;
    }
}

function openExternalLink(url: string): void {
    const isTMA = typeof window !== 'undefined' && Boolean(window.Telegram?.WebApp?.initData);
    if (isTMA && window.Telegram?.WebApp?.openLink) {
        window.Telegram.WebApp.openLink(url);
        return;
    }
    window.location.href = url;
}

export const useSubscriptionActions = ({
    plans,
    isBrowserDebug,
    webAppBrowserDebug,
}: UseSubscriptionActionsParams): UseSubscriptionActionsResult => {
    const billing = useBilling();

    const [loadingPlanCode, setLoadingPlanCode] = useState<PlanCode | null>(null);
    const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);

    // anti double-click / concurrent requests
    const inFlightRef = useRef<Set<string>>(new Set());

    const withLock = useCallback(async (key: string, fn: () => Promise<void>) => {
        if (inFlightRef.current.has(key)) return;
        inFlightRef.current.add(key);
        try {
            await fn();
        } finally {
            inFlightRef.current.delete(key);
        }
    }, []);

    const handleSelectPlan = useCallback(
        async (planCode: PlanCode) => {
            // Block payments in browser debug mode
            if (isBrowserDebug || webAppBrowserDebug) {
                showToast('Платежи недоступны в режиме отладки браузера');
                return;
            }

            const lockKey = `payment:${planCode}`;
            await withLock(lockKey, async () => {
                if (loadingPlanCode) return;

                const plan = plans.find((p) => p.code === planCode);
                if (!plan) {
                    showToast('Тариф не найден');
                    return;
                }

                setLoadingPlanCode(planCode);
                try {
                    const { confirmation_url } = await api.createPayment({
                        plan_code: planCode,
                        save_payment_method: true,
                    });

                    if (!confirmation_url || typeof confirmation_url !== 'string') {
                        showToast('Не удалось получить ссылку на оплату');
                        return;
                    }

                    // SECURITY: prevent open redirect / phishing
                    if (!isAllowedPaymentUrl(confirmation_url)) {
                        showToast('Некорректная ссылка оплаты. Попробуйте позже.');
                        return;
                    }

                    // Set polling flag BEFORE redirect to resume polling after return
                    setPollingFlagForPayment({ targetPlanCode: planCode });

                    openExternalLink(confirmation_url);
                } catch (error) {
                    console.error('[billing] createPayment error:', error);
                    const msg = error instanceof Error ? error.message : 'Ошибка при оформлении подписки';
                    showToast(msg);
                } finally {
                    setLoadingPlanCode(null);
                }
            });
        },
        [isBrowserDebug, webAppBrowserDebug, withLock, loadingPlanCode, plans],
    );

    const handleToggleAutoRenew = useCallback(async () => {
        const lockKey = 'autorenew:toggle';

        await withLock(lockKey, async () => {
            if (togglingAutoRenew) return;

            const current = billing.subscription;
            const autoRenewAvailable = current?.autorenew_available ?? false;
            const autoRenewEnabled = current?.autorenew_enabled ?? false;

            if (!autoRenewAvailable) {
                showToast('Автопродление недоступно — привяжите карту');
                return;
            }

            setTogglingAutoRenew(true);
            try {
                // Real toggle (SSOT is current subscription state)
                await billing.setAutoRenew(!autoRenewEnabled);
                showToast(autoRenewEnabled ? 'Автопродление отключено' : 'Автопродление включено');
            } catch (error) {
                console.error('[billing] setAutoRenew error:', error);
                showToast('Не удалось изменить настройки автопродления');
            } finally {
                setTogglingAutoRenew(false);
            }
        });
    }, [withLock, togglingAutoRenew, billing]);

    const handleAddCard = useCallback(async () => {
        const lockKey = 'card:bind';

        await withLock(lockKey, async () => {
            if (togglingAutoRenew) return;

            setTogglingAutoRenew(true);
            try {
                // addPaymentMethod likely redirects internally; if it returns URL, backend should enforce allowlist
                await billing.addPaymentMethod();
            } catch (error) {
                console.error('[billing] addPaymentMethod error:', error);
                let errorMessage = 'Не удалось запустить привязку карты';
                if (error instanceof Error && error.message) {
                    // support structured JSON errors
                    try {
                        const data = JSON.parse(error.message);
                        errorMessage = data?.message || errorMessage;
                    } catch {
                        errorMessage = error.message || errorMessage;
                    }
                }
                showToast(errorMessage);
            } finally {
                setTogglingAutoRenew(false);
            }
        });
    }, [withLock, togglingAutoRenew, billing]);

    return {
        loadingPlanCode,
        togglingAutoRenew,
        handleSelectPlan,
        handleToggleAutoRenew,
        handleAddCard,
    };
};
