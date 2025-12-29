import { useState, useRef } from 'react';
import type { SubscriptionPlan } from '../../../types/billing';
import { api } from '../../../services/api';
import { useBilling } from '../../../contexts/BillingContext';
import { showToast } from '../utils/notify';
import { setPollingFlagForPayment } from './usePaymentPolling';

export type PlanCode = string;

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

/**
 * Hook for managing subscription actions (payments, auto-renew, card binding)
 * Encapsulates all payment-related business logic for reusability across components
 * Includes anti-double-click protection via in-flight request tracking
 * Integrates with payment polling for automatic status updates after payment
 */
export const useSubscriptionActions = ({
    plans,
    isBrowserDebug,
    webAppBrowserDebug,
}: UseSubscriptionActionsParams): UseSubscriptionActionsResult => {
    const billing = useBilling();
    const [loadingPlanCode, setLoadingPlanCode] = useState<PlanCode | null>(null);
    const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);

    // In-flight request lock to prevent double-clicks
    const inFlightRef = useRef<Set<string>>(new Set());

    /**
     * Handle plan selection and payment flow
     * Protected against double-click via in-flight lock
     * Sets polling flag for automatic status update after return from payment
     */
    const handleSelectPlan = async (planCode: PlanCode) => {
        const lockKey = `payment-${planCode}`;

        // Check both loading state and in-flight lock
        if (loadingPlanCode || inFlightRef.current.has(lockKey)) {
            return;
        }

        // Block payments in browser debug mode
        if (isBrowserDebug || webAppBrowserDebug) {
            showToast('Платежи недоступны в режиме отладки браузера');
            return;
        }

        const isTMA = typeof window !== 'undefined' && window.Telegram?.WebApp?.initData;

        // Acquire lock
        inFlightRef.current.add(lockKey);

        try {
            setLoadingPlanCode(planCode);
            const plan = plans.find(p => p.code === planCode);
            if (!plan) throw new Error("Plan not found");

            const { confirmation_url } = await api.createPayment({
                plan_code: planCode,
                save_payment_method: true
            });

            // Set polling flag BEFORE redirect to ensure polling starts on return
            setPollingFlagForPayment();

            // Open payment URL in Telegram or browser
            if (isTMA && window.Telegram) {
                window.Telegram.WebApp.openLink(confirmation_url);
            } else {
                window.location.href = confirmation_url;
            }
        } catch (error) {
            console.error("Subscription error:", error);
            const errorMessage = error instanceof Error ? error.message : "Ошибка при оформлении подписки";
            showToast(errorMessage);
        } finally {
            // Release lock
            inFlightRef.current.delete(lockKey);
            setLoadingPlanCode(null);
        }
    };

    /**
     * Toggle auto-renew for subscription
     * Protected against double-click
     */
    const handleToggleAutoRenew = async () => {
        const lockKey = 'toggle-autorenew';

        if (togglingAutoRenew || inFlightRef.current.has(lockKey)) {
            return;
        }

        inFlightRef.current.add(lockKey);

        try {
            setTogglingAutoRenew(true);
            await billing.toggleAutoRenew(true);
            showToast("Автопродление включено");
        } catch (error) {
            showToast("Не удалось изменить настройки автопродления");
        } finally {
            inFlightRef.current.delete(lockKey);
            setTogglingAutoRenew(false);
        }
    };

    /**
     * Add payment method (bind card)
     * Protected against double-click
     */
    const handleAddCard = async () => {
        const lockKey = 'bind-card';

        if (togglingAutoRenew || inFlightRef.current.has(lockKey)) {
            return;
        }

        inFlightRef.current.add(lockKey);

        try {
            setTogglingAutoRenew(true);
            await billing.addPaymentMethod();
        } catch (error) {
            let errorMessage = "Не удалось запустить привязку карты";
            try {
                const errorData = JSON.parse((error as Error).message);
                errorMessage = errorData.message || errorMessage;
            } catch {
                errorMessage = (error as Error).message || errorMessage;
            }
            showToast(errorMessage);
        } finally {
            inFlightRef.current.delete(lockKey);
            setTogglingAutoRenew(false);
        }
    };

    return {
        loadingPlanCode,
        togglingAutoRenew,
        handleSelectPlan,
        handleToggleAutoRenew,
        handleAddCard,
    };
};
