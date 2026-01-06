// billing/utils/planCardState.tsx
import React from 'react';
import type { SubscriptionPlan, SubscriptionDetails, BillingMe } from '../../../types/billing';
import type { PlanCode } from './types';
import { Loader2 } from 'lucide-react';
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

function ProPanelShell({ children }: { children: React.ReactNode }) {
    return <div className="space-y-3">{children}</div>;
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
    navigate,
}: BuildPlanCardStateParams): PlanCardState => {
    let isCurrent = false;
    let customButtonText: string | undefined;
    let disabled = false;
    let bottomContent: React.ReactNode | undefined;

    if (!subscription) {
        return { isCurrent, disabled, customButtonText, bottomContent };
    }

    const userPlanCode: PlanCode =
        (billing.billingMe?.plan_code as PlanCode) ||
        (subscription.plan === 'free' ? 'FREE' : 'PRO_MONTHLY');

    // FREE card
    if (plan.code === 'FREE') {
        if (subscription.plan === 'pro' && subscription.is_active) {
            disabled = true;
            customButtonText = 'Базовый доступ';
        } else if (subscription.plan === 'free') {
            isCurrent = true;
            disabled = true;
            customButtonText = 'Ваш текущий тариф';
        }
        return { isCurrent, disabled, customButtonText, bottomContent };
    }

    // PRO cards
    const planCode = plan.code as PlanCode;

    // Active PRO on this exact plan
    if (userPlanCode === planCode) {
        isCurrent = true;

        const autoRenew = subscription.autorenew_enabled;
        const paymentMethod = subscription.payment_method;
        const hasCard = paymentMethod?.is_attached ?? false;

        bottomContent = (
            <ProPanelShell>
                <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-3 text-center">
                    <p className="text-[12px] sm:text-[13px] font-bold text-slate-100 uppercase tracking-wide">
                        Доступ до {formatDate(expiresAt)}
                    </p>
                </div>

                {hasCard && autoRenew ? (
                    <>
                        <div className="flex items-center justify-center gap-2 text-[11px] font-bold text-emerald-400 uppercase tracking-widest">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                            <span>Автопродление активно</span>
                        </div>
                        <p className="text-[11px] text-center text-slate-500 font-medium tabular-nums">
                            Карта {paymentMethod?.card_mask || '•••• 0000'}
                        </p>
                        <button
                            onClick={() => navigate('/settings')}
                            className="w-full text-center text-[11px] font-bold text-slate-400 hover:text-white transition-colors uppercase tracking-wide"
                        >
                            Управлять подпиской
                        </button>
                    </>
                ) : hasCard && !autoRenew ? (
                    <>
                        <div className="flex items-center justify-center gap-2 text-[11px] font-bold text-rose-400 uppercase tracking-widest">
                            <span className="w-1.5 h-1.5 rounded-full bg-rose-400/80" />
                            <span>Автопродление выключено</span>
                        </div>
                        <button
                            onClick={handleToggleAutoRenew}
                            disabled={togglingAutoRenew}
                            className="w-full h-10 bg-slate-100 text-slate-900 rounded-lg text-xs font-black hover:bg-white transition-colors flex items-center justify-center gap-2 uppercase tracking-tight disabled:opacity-60"
                        >
                            {togglingAutoRenew && <Loader2 className="animate-spin" size={14} />}
                            Включить продление
                        </button>
                    </>
                ) : (
                    <>
                        <div className="flex items-center justify-center gap-2 text-[11px] font-bold text-amber-400 uppercase tracking-widest">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-400/80" />
                            <span>Оплата не настроена</span>
                        </div>
                        <button
                            onClick={handleAddCard}
                            disabled={togglingAutoRenew}
                            className="w-full h-10 bg-white text-slate-900 rounded-lg text-xs font-black hover:bg-slate-50 transition-colors flex items-center justify-center gap-2 uppercase tracking-tight disabled:opacity-60"
                        >
                            Привязать карту
                        </button>
                    </>
                )}
            </ProPanelShell>
        );

        return { isCurrent, disabled, customButtonText, bottomContent };
    }

    // User is PRO but on different plan (disable others)
    if (isPro) {
        disabled = true;
        customButtonText = 'Доступно по подписке';
        return { isCurrent, disabled, customButtonText, bottomContent };
    }

    // Expired PRO
    if (isExpired) {
        bottomContent = (
            <ProPanelShell>
                <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl p-3 text-center">
                    <p className="text-xs font-bold text-rose-400 uppercase tracking-tight">
                        Подписка истекла {formatDate(expiresAt)}
                    </p>
                </div>

                <button
                    onClick={() => handleSelectPlan(planCode)}
                    disabled={loadingPlanCode === planCode}
                    className="w-full h-11 bg-white text-slate-900 rounded-xl font-bold text-sm hover:bg-slate-50 transition-all flex items-center justify-center gap-2 disabled:opacity-60"
                >
                    {loadingPlanCode === planCode ? <Loader2 className="animate-spin" size={16} /> : `Восстановить за ${plan.price} ₽`}
                </button>
            </ProPanelShell>
        );
    }

    return { isCurrent, disabled, customButtonText, bottomContent };
};
