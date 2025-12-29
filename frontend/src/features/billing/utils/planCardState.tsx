import React from 'react';
import type { SubscriptionPlan } from '../../../types/billing';
import type { PlanCode } from '../hooks/useSubscriptionActions';
import { Loader2 } from 'lucide-react';
import type { SubscriptionDetails, BillingMe } from '../../../types/billing';
import { formatDate } from './date';

interface BillingContextData {
    subscription: SubscriptionDetails | null;
    billingMe: BillingMe | null;
}

interface PlanCardState {
    isCurrent: boolean;
    disabled: boolean;
    customButtonText?: string;
    bottomContent?: React.ReactNode;
}

interface BuildPlanCardStateParams {
    plan: SubscriptionPlan;
    subscription: SubscriptionDetails | null;
    billing: BillingContextData;
    isPro: boolean;
    isExpired: boolean;
    expiresAt: string | null;
    loadingPlanCode: PlanCode | null;
    togglingAutoRenew: boolean;
    handleSelectPlan: (planCode: PlanCode) => void;
    handleToggleAutoRenew: () => void;
    handleAddCard: () => void;
    navigate: (path: string) => void;
}

export const buildPlanCardState = ({
    plan,
    subscription,
    billing,
    isPro,
    isExpired,
    expiresAt,
    loadingPlanCode,
    togglingAutoRenew,
    handleSelectPlan,
    handleToggleAutoRenew,
    handleAddCard,
    navigate
}: BuildPlanCardStateParams): PlanCardState => {
    let isCurrent = false;
    let customButtonText: string | undefined;
    let disabled = false;
    let bottomContent: React.ReactNode | undefined;

    if (!subscription) {
        return { isCurrent, disabled, customButtonText, bottomContent };
    }

    // Use proper plan codes - no legacy MONTHLY/YEARLY
    const userPlanCode = billing.billingMe?.plan_code ||
        (subscription.plan === 'free' ? 'FREE' : 'PRO_MONTHLY');

    // FREE CARD
    if (plan.code === 'FREE') {
        if (subscription.plan === 'pro' && subscription.is_active) {
            isCurrent = false;
            disabled = true;
            customButtonText = "Базовый доступ";
        } else if (subscription.plan === 'free') {
            isCurrent = true;
            disabled = true;
            customButtonText = "Ваш текущий тариф";
        }
    }
    // PRO CARDS
    else {
        // plan.code is already 'PRO_MONTHLY' or 'PRO_YEARLY'
        const currentPlanCode = plan.code;

        // If this specific PRO plan is active
        if (userPlanCode === currentPlanCode) {
            isCurrent = true;

            const autoRenew = subscription.autorenew_enabled;
            const paymentMethod = subscription.payment_method;
            const hasCard = paymentMethod?.is_attached ?? false;

            bottomContent = (
                <div className="space-y-4 mt-auto">
                    {/* Expiration Badge */}
                    <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-3 text-center">
                        <p className="text-[13px] font-bold text-slate-100 uppercase tracking-wide">
                            Доступ до {formatDate(expiresAt)}
                        </p>
                    </div>

                    {/* Auto-renew Status */}
                    <div className="space-y-3">
                        {hasCard && autoRenew ? (
                            // Variant 1: Auto-renew ON
                            <>
                                <div className="flex items-center justify-center gap-2 text-xs font-bold text-emerald-400 uppercase tracking-widest">
                                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                                    <span>Автопродление активно</span>
                                </div>
                                <p className="text-[11px] text-center text-slate-500 font-medium">
                                    Карта {paymentMethod?.card_mask || '•••• 0000'}
                                </p>
                                <button
                                    onClick={() => navigate('/settings')}
                                    className="w-full text-center text-[11px] font-bold text-slate-400 hover:text-white transition-colors"
                                >
                                    УПРАВЛЯТЬ ПОДПИСКОЙ
                                </button>
                            </>
                        ) : hasCard && !autoRenew ? (
                            // Variant 2: Auto-renew OFF
                            <>
                                <div className="flex items-center justify-center gap-2 text-xs font-bold text-rose-400 uppercase tracking-widest">
                                    <span>○</span>
                                    <span>Автопродление выключено</span>
                                </div>
                                <button
                                    onClick={handleToggleAutoRenew}
                                    disabled={togglingAutoRenew}
                                    className="w-full h-10 bg-slate-100 text-slate-900 rounded-lg text-xs font-black hover:bg-white transition-colors flex items-center justify-center gap-2 uppercase tracking-tight"
                                >
                                    {togglingAutoRenew && <Loader2 className="animate-spin" size={14} />}
                                    Включить продление
                                </button>
                            </>
                        ) : (
                            // Variant 3: No Card
                            <>
                                <div className="flex items-center justify-center gap-2 text-xs font-bold text-amber-400 uppercase tracking-widest">
                                    <span>⚠</span>
                                    <span>Оплата не настроена</span>
                                </div>
                                <button
                                    onClick={handleAddCard}
                                    disabled={togglingAutoRenew}
                                    className="w-full h-10 bg-white text-slate-900 rounded-lg text-xs font-black hover:bg-slate-50 transition-colors flex items-center justify-center gap-2 uppercase tracking-tight"
                                >
                                    Привязать карту
                                </button>
                            </>
                        )}
                    </div>
                </div>
            );
        }
        // If User is PRO but on DIFFERENT plan (e.g. Monthly vs Yearly)
        else if (isPro) {
            disabled = true;
            customButtonText = "Доступно по подписке";
        }
        // State C: Expired Pro (User is Free now, but was Pro)
        else if (isExpired) {
            bottomContent = (
                <div className="space-y-3 mt-auto">
                    <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl p-3 text-center">
                        <p className="text-xs font-bold text-rose-400 uppercase tracking-tight">
                            Подписка истекла {formatDate(expiresAt)}
                        </p>
                    </div>
                    <button
                        onClick={() => handleSelectPlan(plan.code)}
                        disabled={loadingPlanCode === plan.code}
                        className="w-full h-11 bg-white text-slate-900 rounded-xl font-bold text-sm hover:bg-slate-50 transition-all flex items-center justify-center gap-2"
                    >
                        {loadingPlanCode === plan.code ? (
                            <Loader2 className="animate-spin" size={16} />
                        ) : (
                            `Восстановить за ${plan.price} ₽`
                        )}
                    </button>
                </div>
            );
        }
    }

    return { isCurrent, disabled, customButtonText, bottomContent };
};
