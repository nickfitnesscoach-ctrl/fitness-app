import React from 'react';
import { useNavigate } from 'react-router-dom';
import PlanCard from '../components/PlanCard';
import { useBilling } from '../../../contexts/BillingContext';
import { useAuth } from '../../../contexts/AuthContext';
import { Loader2 } from 'lucide-react';
import { useTelegramWebApp } from '../../../hooks/useTelegramWebApp';
import { useSubscriptionPlans } from '../hooks/useSubscriptionPlans';
import { useSubscriptionStatus } from '../hooks/useSubscriptionStatus';
import { useSubscriptionActions } from '../hooks/useSubscriptionActions';
import { SubscriptionHeader } from '../components/subscription/SubscriptionHeader';
import { buildPlanCardState } from '../utils/planCardState';
import { PageContainer } from '../../../components/shared/PageContainer';

const SubscriptionPage: React.FC = () => {
    const billing = useBilling();
    const navigate = useNavigate();
    const { isBrowserDebug } = useAuth();
    const { isReady, isTelegramWebApp: webAppDetected, isBrowserDebug: webAppBrowserDebug } = useTelegramWebApp();

    const { plans, loading: loadingPlans, error } = useSubscriptionPlans();
    const subscriptionStatus = useSubscriptionStatus(billing.subscription);

    const {
        loadingPlanId,
        togglingAutoRenew,
        handleSelectPlan,
        handleToggleAutoRenew,
        handleAddCard
    } = useSubscriptionActions({
        plans,
        isBrowserDebug,
        webAppBrowserDebug,
    });

    if (!isReady) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    if (!webAppDetected && !isBrowserDebug && !webAppBrowserDebug) {
        return (
            <div className="min-h-screen flex items-center justify-center p-4">
                <div className="bg-orange-50 border-2 border-orange-200 rounded-2xl p-6 text-center max-w-md">
                    <h2 className="text-xl font-bold text-orange-900 mb-2">Откройте через Telegram</h2>
                    <p className="text-orange-700">Приложение работает только внутри Telegram.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <PageContainer withSafeTop={true} className="pt-2 pb-10 space-y-6">
                <SubscriptionHeader
                    topStatusText={subscriptionStatus.topStatusText}
                    headerTitle={subscriptionStatus.headerTitle}
                    headerSubtitle={subscriptionStatus.headerSubtitle}
                />

                <div className="flex flex-col gap-4">
                    {loadingPlans ? (
                        <div className="flex flex-col items-center justify-center py-20 space-y-4">
                            <Loader2 className="animate-spin text-slate-400" size={32} />
                            <p className="text-sm text-slate-400 font-medium">Загружаем тарифы...</p>
                        </div>
                    ) : error ? (
                        <div className="text-center p-6 bg-red-50 rounded-2xl border border-red-100">
                            <p className="text-sm text-red-600 font-medium">{error}</p>
                        </div>
                    ) : plans.map((plan) => {
                        const cardState = buildPlanCardState({
                            plan,
                            subscription: billing.subscription,
                            billing: {
                                subscription: billing.subscription,
                                billingMe: billing.billingMe
                            },
                            isPro: subscriptionStatus.isPro,
                            isExpired: subscriptionStatus.isExpired,
                            expiresAt: billing.subscription?.expires_at ?? null,
                            loadingPlanId,
                            togglingAutoRenew,
                            handleSelectPlan,
                            handleToggleAutoRenew,
                            handleAddCard,
                            navigate
                        });

                        return (
                            <PlanCard
                                key={plan.id}
                                plan={plan}
                                isCurrent={cardState.isCurrent}
                                isLoading={loadingPlanId === plan.id}
                                onSelect={handleSelectPlan}
                                customButtonText={cardState.customButtonText}
                                disabled={cardState.disabled}
                                bottomContent={cardState.bottomContent}
                            />
                        );
                    })}
                </div>

                <div className="px-4">
                    <p className="text-center text-[10px] text-slate-400 leading-relaxed uppercase tracking-wider opacity-60">
                        Нажимая кнопку, вы соглашаетесь с условиями использования и политикой конфиденциальности.
                        Подписка продлевается автоматически, отмена в любое время.
                    </p>
                </div>
            </PageContainer>
        </div>
    );
};

export default SubscriptionPage;
