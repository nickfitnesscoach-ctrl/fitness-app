import React from 'react';
import type { SubscriptionPlan, SubscriptionDetails, BillingMe } from '../../../types/billing';
import { isPlanCode, type PlanCode } from '../types';
import { Loader2 } from 'lucide-react';
import { formatDate } from './date';

/**
 * SSOT Data Context for billing UI.
 *
 * Contains the two primary data sources for subscription state:
 * - `subscription`: General subscription status (is_active, autorenew, payment_method)
 * - `billingMe`: Exact plan details (plan_code = FREE/PRO_MONTHLY/PRO_YEARLY)
 *
 * If billingMe.plan_code is missing, DO NOT guess — use subscription.plan instead.
 */
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

/**
 * Parameters for buildPlanCardState.
 *
 * SSOT Responsibilities:
 * - `billing.subscription` — source of truth for subscription status
 *   (is_active, payment_method, autorenew_enabled)
 * - `billing.billingMe` — source of truth for exact plan flavor
 *   (plan_code: FREE | PRO_MONTHLY | PRO_YEARLY)
 */
interface BuildPlanCardStateParams {
    plan: SubscriptionPlan;
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

/** Единая “плашка” с датой окончания доступа */
function ProUntilPanel({ expiresAt }: { expiresAt: string | null }) {
    return (
        <div className="bg-slate-800/50 border border-slate-700/50 rounded-xl p-3 text-center">
            <p className="text-[12px] sm:text-[13px] font-bold text-slate-100 uppercase tracking-wide">
                Доступ до {formatDate(expiresAt)}
            </p>
        </div>
    );
}

/** Универсальная кнопка управления подпиской */
function ManageSubscriptionLink({ onClick }: { onClick: () => void }) {
    return (
        <button
            onClick={onClick}
            className="w-full text-center text-[11px] font-bold text-slate-400 hover:text-white transition-colors uppercase tracking-wide"
        >
            Управлять подпиской
        </button>
    );
}

/** Маленький статус-текст (оплата не настроена / автопродление активно / выключено) */
function ProStatusLine({
    variant,
    children,
    pulse,
}: {
    variant: 'amber' | 'emerald' | 'rose';
    children: React.ReactNode;
    pulse?: boolean;
}) {
    const color =
        variant === 'amber'
            ? 'text-amber-400'
            : variant === 'emerald'
                ? 'text-emerald-400'
                : 'text-rose-400';

    const dot =
        variant === 'amber'
            ? 'bg-amber-400/80'
            : variant === 'emerald'
                ? 'bg-emerald-400'
                : 'bg-rose-400/80';

    return (
        <div className={`flex items-center justify-center gap-2 text-[11px] font-bold ${color} uppercase tracking-widest`}>
            <span className={`w-1.5 h-1.5 rounded-full ${dot} ${pulse ? 'animate-pulse' : ''}`} />
            <span>{children}</span>
        </div>
    );
}

// isPlanCode imported from ../types (SSOT)

/**
 * Главная идея этой функции:
 * Мы НЕ “рисуем карточку”, а принимаем решение, КАК её показывать пользователю.
 * (какой текст, какие кнопки, что доступно сейчас)
 */
export const buildPlanCardState = ({
    plan,
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
    // Базовые значения по умолчанию (ничего не выбрано, всё доступно)
    let isCurrent = false;
    let customButtonText: string | undefined;
    let disabled = false;
    let bottomContent: React.ReactNode | undefined;

    // Если подписка ещё не загружена — не пытаемся “угадывать” состояние
    const subscription = billing.subscription;
    if (!subscription) {
        return { isCurrent, disabled, customButtonText, bottomContent };
    }

    const isProActive = subscription.plan === 'pro' && Boolean(subscription.is_active);

    /**
     * В идеале backend должен отдавать точный plan_code (PRO_MONTHLY / PRO_YEARLY).
     * Если не отдал — мы НЕ гадаем.
     */
    const userPlanCode = isPlanCode(billing.billingMe?.plan_code) ? (billing.billingMe!.plan_code as PlanCode) : null;

    // ---------- Сценарий 1: карточка FREE ----------
    if (plan.code === 'FREE') {
        // Если сейчас активен PRO — Free остаётся “как базовый доступ”, но кликать нельзя
        if (isProActive) {
            disabled = true;
            customButtonText = 'Базовый доступ';
            return { isCurrent, disabled, customButtonText, bottomContent };
        }

        // Если пользователь реально на free — показываем “текущий тариф”
        if (subscription.plan === 'free') {
            isCurrent = true;
            disabled = true;
            customButtonText = 'Ваш текущий тариф';
        }

        return { isCurrent, disabled, customButtonText, bottomContent };
    }

    const planCode = plan.code as PlanCode;

    // ---------- Сценарий 2: PRO активен, но точный plan_code неизвестен ----------
    if (isProActive && !userPlanCode) {
        disabled = true;
        customButtonText = 'PRO активен';

        const autoRenew = subscription.autorenew_enabled;
        const paymentMethod = subscription.payment_method;
        const hasCard = paymentMethod?.is_attached ?? false;

        bottomContent = (
            <ProPanelShell>
                <ProUntilPanel expiresAt={expiresAt} />
                <ManageSubscriptionLink onClick={() => navigate('/settings')} />

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

    // ---------- Сценарий 3: PRO активен и точный plan_code известен ----------
    if (userPlanCode && userPlanCode === planCode) {
        isCurrent = true;

        const autoRenew = subscription.autorenew_enabled;
        const paymentMethod = subscription.payment_method;
        const hasCard = paymentMethod?.is_attached ?? false;

        bottomContent = (
            <ProPanelShell>
                <ProUntilPanel expiresAt={expiresAt} />

                {hasCard && autoRenew ? (
                    <>
                        <ProStatusLine variant="emerald" pulse>
                            Автопродление активно
                        </ProStatusLine>

                        <p className="text-[11px] text-center text-slate-500 font-medium tabular-nums">
                            Карта {paymentMethod?.card_mask || '•••• 0000'}
                        </p>

                        <ManageSubscriptionLink onClick={() => navigate('/settings')} />
                    </>
                ) : hasCard && !autoRenew ? (
                    <>
                        <ProStatusLine variant="rose">Автопродление выключено</ProStatusLine>

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
                        <ProStatusLine variant="amber">Оплата не настроена</ProStatusLine>

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

    // ---------- Сценарий 4: у пользователя уже активен PRO, но это другой план ----------
    if (isPro) {
        disabled = true;
        customButtonText = 'Доступно по подписке';
        return { isCurrent, disabled, customButtonText, bottomContent };
    }

    // ---------- Сценарий 5: PRO истёк → предлагаем восстановить ----------
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
