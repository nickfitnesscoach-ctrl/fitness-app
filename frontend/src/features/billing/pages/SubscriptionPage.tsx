import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import PlanCard from '../components/PlanCard';
import { useBilling } from '../../../contexts/BillingContext';
import { useAuth } from '../../../contexts/AuthContext';
import { useTelegramWebApp } from '../../../hooks/useTelegramWebApp';
import { useSubscriptionPlans } from '../hooks/useSubscriptionPlans';
import { useSubscriptionStatus } from '../hooks/useSubscriptionStatus';
import { useSubscriptionActions } from '../hooks/useSubscriptionActions';
import { SubscriptionHeader } from '../components/SubscriptionHeader';
import { buildPlanCardState } from '../utils/planCardState';
import { PageContainer } from '../../../components/shared/PageContainer';
import { getPlanCopy } from '../config/planCopy';



const SubscriptionPage: React.FC = () => {
    const billing = useBilling();
    const navigate = useNavigate();
    const { isBrowserDebug } = useAuth();
    const { isReady, isTelegramWebApp: webAppDetected, isBrowserDebug: webAppBrowserDebug } = useTelegramWebApp();

    const { plans, loading: loadingPlans, error } = useSubscriptionPlans();

    const subscriptionStatus = useSubscriptionStatus(billing.subscription);

    const {
        loadingPlanCode,
        togglingAutoRenew,
        handleSelectPlan,
        handleToggleAutoRenew,
        handleAddCard,
    } = useSubscriptionActions({
        plans,
        isBrowserDebug,
        webAppBrowserDebug,
    });

    // ✅ ВАЖНО: хуки уже все вызваны — дальше можно делать любые early return
    if (!isReady) {
        return (
            <div className="flex items-center justify-center py-16">
                <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full" />
            </div>
        );
    }

    const isAllowedOutsideTelegram = isBrowserDebug || webAppBrowserDebug;
    if (!webAppDetected && !isAllowedOutsideTelegram) {
        return (
            <div className="flex items-center justify-center p-4 py-16">
                <div className="bg-orange-50 border-2 border-orange-200 rounded-2xl p-6 text-center max-w-md">
                    <h2 className="text-xl font-bold text-orange-900 mb-2">Откройте через Telegram</h2>
                    <p className="text-orange-700">Приложение работает только внутри Telegram.</p>
                </div>
            </div>
        );
    }

    // Обычный объект — проще и безопаснее, чем useMemo (меньше хуков = меньше шансов сломать Rules of Hooks)
    const cardContext = {
        billing: {
            subscription: billing.subscription,
            billingMe: billing.billingMe,
        },
        isPro: subscriptionStatus.isPro,
        isExpired: subscriptionStatus.isExpired,
        expiresAt: billing.subscription?.expires_at ?? null,
        loadingPlanCode,
        togglingAutoRenew,
        handleSelectPlan,
        handleToggleAutoRenew,
        handleAddCard,
        navigate,
    };

    return (
        <div className="flex-1 bg-gradient-to-br from-blue-50 via-white to-purple-50">
            <PageContainer withSafeTop className="py-6 space-y-[var(--section-gap)]">
                <div className="flex flex-col gap-5">
                    <SubscriptionHeader
                        topStatusText={subscriptionStatus.topStatusText}
                        headerTitle={subscriptionStatus.headerTitle}
                        headerSubtitle={subscriptionStatus.headerSubtitle}
                    />

                    <div className="flex flex-col gap-3">
                        <div className="flex flex-col gap-4 animate-in fade-in slide-in-from-bottom-4 duration-500">
                            {loadingPlans && (
                                <div className="flex flex-col items-center justify-center py-16 gap-3">
                                    <Loader2 className="animate-spin text-slate-400" size={28} />
                                    <p className="text-sm text-slate-400 font-medium">Загружаем тарифы...</p>
                                </div>
                            )}

                            {!loadingPlans && error && (
                                <div className="text-center p-6 bg-red-50 rounded-2xl border border-red-100">
                                    <p className="text-sm text-red-600 font-medium">{error}</p>
                                </div>
                            )}

                            {!loadingPlans &&
                                !error &&
                                [...plans]
                                    .sort((a, b) => {
                                        // Stable sort: by order from PLAN_COPY, then by code
                                        const orderDiff = getPlanCopy(a.code).order - getPlanCopy(b.code).order;
                                        return orderDiff !== 0 ? orderDiff : a.code.localeCompare(b.code);
                                    })
                                    .map((plan) => {
                                        const cardState = buildPlanCardState({ plan, ...cardContext });

                                        return (
                                            <PlanCard
                                                key={plan.code}
                                                plan={plan}
                                                isCurrent={cardState.isCurrent}
                                                isLoading={loadingPlanCode === plan.code}
                                                onSelect={handleSelectPlan}
                                                customButtonText={cardState.customButtonText}
                                                disabled={cardState.disabled}
                                                bottomContent={cardState.bottomContent}
                                            />
                                        );
                                    })}
                        </div>

                        <div className="max-w-md mx-auto text-center text-[10px] text-slate-400 leading-tight uppercase tracking-wider opacity-60">
                            <span className="block">
                                Нажимая кнопку, вы соглашаетесь с условиями использования и политикой конфиденциальности.
                            </span>
                            <span className="block mt-0.5">Подписка продлевается автоматически, отмена в любое время.</span>
                        </div>
                    </div>
                </div>
            </PageContainer>
        </div>
    );
};

export default SubscriptionPage;
