import { useState } from 'react';
import { PlanId, Plan } from '../components/PlanCard';
import { api } from '../services/api';
import { useBilling } from '../contexts/BillingContext';

interface UseSubscriptionActionsParams {
    plans: Plan[];
    isBrowserDebug: boolean;
    webAppBrowserDebug: boolean;
}

interface UseSubscriptionActionsResult {
    loadingPlanId: PlanId | null;
    togglingAutoRenew: boolean;
    handleSelectPlan: (planId: PlanId) => Promise<void>;
    handleToggleAutoRenew: () => Promise<void>;
    handleAddCard: () => Promise<void>;
}

/**
 * Hook for managing subscription actions (payments, auto-renew, card binding)
 * Encapsulates all payment-related business logic for reusability across components
 */
export const useSubscriptionActions = ({
    plans,
    isBrowserDebug,
    webAppBrowserDebug,
}: UseSubscriptionActionsParams): UseSubscriptionActionsResult => {
    const billing = useBilling();
    const [loadingPlanId, setLoadingPlanId] = useState<PlanId | null>(null);
    const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);

    /**
     * Show toast notification using Telegram WebApp API or browser alert
     */
    const showToast = (message: string) => {
        const tg = window.Telegram?.WebApp;
        if (tg?.showAlert) {
            tg.showAlert(message);
        } else {
            alert(message);
        }
    };

    /**
     * Handle plan selection and payment flow
     */
    const handleSelectPlan = async (planId: PlanId) => {
        if (loadingPlanId) return;

        // Block payments in browser debug mode
        if (isBrowserDebug || webAppBrowserDebug) {
            showToast('Платежи недоступны в режиме отладки браузера');
            return;
        }

        const isTMA = typeof window !== 'undefined' && window.Telegram?.WebApp?.initData;

        try {
            setLoadingPlanId(planId);
            const plan = plans.find(p => p.id === planId);
            if (!plan) throw new Error("Plan not found");

            const { confirmation_url } = await api.createPayment({
                plan_code: plan.code,
                save_payment_method: true
            });

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
            setLoadingPlanId(null);
        }
    };

    /**
     * Toggle auto-renew for subscription
     */
    const handleToggleAutoRenew = async () => {
        if (togglingAutoRenew) return;
        try {
            setTogglingAutoRenew(true);
            await billing.toggleAutoRenew(true);
            showToast("Автопродление включено");
        } catch (error) {
            showToast("Не удалось изменить настройки автопродления");
        } finally {
            setTogglingAutoRenew(false);
        }
    };

    /**
     * Add payment method (bind card)
     */
    const handleAddCard = async () => {
        if (togglingAutoRenew) return;
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
            setTogglingAutoRenew(false);
        }
    };

    return {
        loadingPlanId,
        togglingAutoRenew,
        handleSelectPlan,
        handleToggleAutoRenew,
        handleAddCard,
    };
};
