import React, { useState } from 'react';
import PlanCard, { Plan, PlanId } from '../components/PlanCard';
import { api } from '../services/api';
import { useBilling } from '../contexts/BillingContext';

const PLANS: Plan[] = [
    {
        id: 'free',
        name: 'Free',
        priceText: '0 ₽',
        features: [
            'До 3 фото в день',
            'Базовый анализ еды',
            'Ограниченная история (7 дней)'
        ]
    },
    {
        id: 'pro_monthly',
        name: 'PRO Plan',
        priceText: '299 ₽ / месяц',
        features: [
            'Безлимитный анализ еды',
            'Персональные рекомендации',
            'История прогресса',
            'Приоритетная поддержка'
        ]
    },
    {
        id: 'pro_yearly',
        name: 'PRO Plan – Год',
        priceText: '2490 ₽ / год',
        oldPriceText: '3588 ₽',
        priceSubtext: '≈ 208 ₽ / месяц',
        tag: 'POPULAR', // Or 'Выбор большинства' / '-30%'
        features: [
            'Безлимитный анализ еды',
            'Персональные рекомендации',
            'История прогресса',
            'Приоритетная поддержка'
        ]
    }
];

const SubscriptionPage: React.FC = () => {
    const billing = useBilling();
    const [loadingPlanId, setLoadingPlanId] = useState<PlanId | null>(null);

    const showToast = (message: string) => {
        // Placeholder for toast notification
        const tg = window.Telegram?.WebApp;
        if (tg?.showAlert) {
            tg.showAlert(message);
        } else {
            alert(message);
        }
    };

    const handleSelectPlan = async (planId: PlanId) => {
        // Prevent selection if already loading or if plan is active (though button should be disabled)
        if (loadingPlanId) return;

        // Check if running in Telegram Mini App
        const isTMA = typeof window !== 'undefined' && window.Telegram?.WebApp?.initData;

        try {
            setLoadingPlanId(planId);

            // Map PlanId to BillingPlanCode
            const planCode = planId === 'pro_monthly' ? 'MONTHLY' : 'YEARLY';

            // Call backend to create payment
            const { confirmation_url } = await api.createPayment({ plan_code: planCode });

            // Open payment URL
            if (isTMA && window.Telegram) {
                // Telegram Mini App: use WebApp API
                window.Telegram.WebApp.openLink(confirmation_url);
            } else {
                // Regular browser: redirect
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

    // Helper to format date
    const formatDate = (dateString: string | null) => {
        if (!dateString) return '';
        return new Date(dateString).toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'numeric',
            year: 'numeric'
        });
    };

    return (
        <div className="p-4 pb-24 space-y-6">
            <div className="text-center space-y-2">
                <h1 className="text-2xl font-bold">Премиум доступ</h1>
                <p className="text-gray-500">Получи максимум от FoodMind AI</p>
            </div>

            <div className="space-y-4">
                {PLANS.map((plan) => {
                    // Determine state for this card
                    let isCurrent = false;
                    let customButtonText: string | undefined;
                    let disabled = false;

                    if (billing.data) {
                        const userPlanCode = billing.data.plan_code;
                        const isPro = ['MONTHLY', 'YEARLY'].includes(userPlanCode);

                        if (plan.id === 'free') {
                            if (userPlanCode === 'FREE') {
                                isCurrent = true;
                            } else {
                                // User is PRO, but looking at FREE card
                                customButtonText = "Базовый бесплатный тариф";
                                disabled = true;
                            }
                        } else {
                            // PRO plans
                            // Map plan.id to code for comparison
                            const planCode = plan.id === 'pro_monthly' ? 'MONTHLY' : 'YEARLY';

                            if (userPlanCode === planCode) {
                                isCurrent = true;
                                if (billing.data.expires_at) {
                                    customButtonText = `Текущий план до ${formatDate(billing.data.expires_at)}`;
                                }
                                disabled = true;
                            } else if (isPro) {
                                // User has DIFFERENT PRO plan (e.g. Monthly vs Yearly)
                                // Allow upgrade/downgrade? 
                                // For now, per requirements, if PRO is active, we might want to disable others or handle switch.
                                // Requirement says: "Если план Pro уже активен... Кнопку отключить (disabled)"
                                // But specifically for the ACTIVE plan. 
                                // Let's assume we allow switching if it's a different PRO plan, 
                                // OR if the requirement implies disabling ALL payment buttons if ANY Pro is active.
                                // "Если пользователь на Pro... На карточке PRO (месячный)... Сделать неактивную кнопку"
                                // Let's follow the specific instruction for the active plan.
                                // If user has Monthly, and looks at Yearly, usually we want to allow upgrade.
                                // But the prompt says: "Итог: у пользователя на «Дневнике» — Pro, а в «Подписке» — как будто он всё ещё на Free."
                                // And "Если план Pro уже активен, не пытаться снова создавать платеж по нажатию" - this likely refers to the active plan.

                                // Let's keep it simple: if it's the current plan, disable it. 
                                // If it's another PRO plan, leave it enabled (upgrade path), unless explicitly told otherwise.
                                // Wait, the prompt says: "На карточке PRO (месячный): Вместо кнопки... Сделать неактивную кнопку... Кнопку отключить".
                                // This applies if the user HAS that plan.
                            }
                        }
                    }

                    return (
                        <PlanCard
                            key={plan.id}
                            plan={plan}
                            isCurrent={isCurrent}
                            isLoading={loadingPlanId === plan.id}
                            onSelect={handleSelectPlan}
                            customButtonText={customButtonText}
                            disabled={disabled}
                        />
                    );
                })}
            </div>

            <p className="text-center text-xs text-gray-400 mt-8">
                Нажимая кнопку, вы соглашаетесь с условиями использования и политикой конфиденциальности.
            </p>
        </div>
    );
};

export default SubscriptionPage;
