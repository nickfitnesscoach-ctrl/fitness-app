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

const PLAN_CODES: PlanCode[] = ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'];
function isPlanCode(v: any): v is PlanCode {
    return typeof v === 'string' && PLAN_CODES.includes(v as PlanCode);
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

    const subscriptionIsProActive = subscription.plan === 'pro' && Boolean(subscription.is_active);

    // Detect exact plan code ONLY if backend provided it
    const userPlanCode = isPlanCode(billing.billingMe?.plan_code) ? (billing.billingMe!.plan_code as PlanCode) : null;

    // FREE card behavior
    if (plan.code === 'FREE') {
        if (subscriptionIsProActive) {
            disabled = true;
            customButtonText = 'Базовый доступ';
        } else if (subscription.plan === 'free') {
            isCurrent = true;
            disabled = true;
            customButtonText = 'Ваш текущий тариф';
        }
        return { isCurrent, disabled, customButtonText, bottomContent };
    }

    const planCode = plan.code as PlanCode;

    // If user has PRO active but plan_code is unknown -> do NOT guess monthly/yearly.
    if (subscriptionIsProActive && !userPlanCode) {
        disabled = true;
        customButtonText = 'PRO активен';

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

                <button
                    onClick={() => navigate('/settings')}
                    className="w-full text-center text-[11px] font-bold text-slate-400 hover:text-white transition-colors uppercase tracking-wide"
                >
                    Управлять подпиской
                </button>

                {!hasCard ? (
                    <div className="text-[11px] text-center text-amber-400 font-bold uppercase tracking-widest">
                        Оплата не настроена
                    </div>
                ) : autoRenew ? (
                    <div className="text-[11px] text-center text-emerald-400 font-bold uppercase tracking-widest">
                        Автопродление активно
                    </div>
                ) : (
                    <div className="text-[11px] text-center text-rose-400 font-bold uppercase tracking-widest">
                        Автопродление выключено
                    </div>
                )}
            </ProPanelShell>
        );

        return { isCurrent, disabled, customButtonText, bottomContent };
    }

    // Active PRO on exact plan
    if (userPlanCode && userPlanCode === planCode) {
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

    // User is PRO (active) but on a different plan -> disable other cards
    if (isPro) {
        disabled = true;
        customButtonText = 'Доступно по подписке';
        return { isCurrent, disabled, customButtonText, bottomContent };
    }

    // Expired PRO -> show restore CTA
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
                    {loadingPlanCode === planCode ? (
                        <Loader2 className="animate-spin" size={16} />
                    ) : (
                        `Восстановить за ${plan.price} ₽`
                    )}
                </button>
            </ProPanelShell>
        );
    }

    return { isCurrent, disabled, customButtonText, bottomContent };
};
