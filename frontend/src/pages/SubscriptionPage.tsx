import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import PlanCard, { Plan, PlanId } from '../components/PlanCard';
import { api } from '../services/api';
import { useBilling } from '../contexts/BillingContext';
import { Loader2 } from 'lucide-react';

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
        tag: 'POPULAR',
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
    const navigate = useNavigate();
    const [loadingPlanId, setLoadingPlanId] = useState<PlanId | null>(null);
    const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);

    const showToast = (message: string) => {
        const tg = window.Telegram?.WebApp;
        if (tg?.showAlert) {
            tg.showAlert(message);
        } else {
            alert(message);
        }
    };

    const handleSelectPlan = async (planId: PlanId) => {
        if (loadingPlanId) return;

        const isTMA = typeof window !== 'undefined' && window.Telegram?.WebApp?.initData;

        try {
            setLoadingPlanId(planId);
            const planCode = planId === 'pro_monthly' ? 'MONTHLY' : 'YEARLY';
            const { confirmation_url } = await api.createPayment({ plan_code: planCode });

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

    const handleToggleAutoRenew = async () => {
        if (togglingAutoRenew) return;
        try {
            setTogglingAutoRenew(true);
            // If currently ON, turn OFF. If OFF, turn ON.
            // But here we only have "Enable" button in one case.
            // Logic:
            // If auto_renew is OFF, we want to turn it ON.
            await billing.toggleAutoRenew(true);
            showToast("Автопродление включено");
        } catch (error) {
            showToast("Не удалось изменить настройки автопродления");
        } finally {
            setTogglingAutoRenew(false);
        }
    };

    const handleAddCard = async () => {
        if (togglingAutoRenew) return;
        try {
            setTogglingAutoRenew(true);
            await billing.addPaymentMethod();
        } catch (error) {
            // Пытаемся распарсить структурированную ошибку
            let errorMessage = "Не удалось запустить привязку карты";
            try {
                const errorData = JSON.parse((error as Error).message);
                errorMessage = errorData.message || errorMessage;
            } catch {
                // Если не JSON, используем сообщение как есть
                errorMessage = (error as Error).message || errorMessage;
            }
            showToast(errorMessage);
        } finally {
            setTogglingAutoRenew(false);
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

    // Determine State - Use new subscription format
    const subscription = billing.subscription;
    const isPro = subscription?.plan === 'pro' && subscription?.is_active;
    const expiresAt = subscription?.expires_at ?? null;
    const isExpired = !isPro && !!expiresAt; // State C: Not Pro, but has expiration date (implies past)

    // Header Text
    let headerTitle = "Премиум доступ";
    let headerSubtitle = "Получи максимум от FoodMind AI";
    let topStatusText = "Текущий тариф: Free";

    if (isPro) {
        topStatusText = `Текущий тариф: PRO до ${formatDate(expiresAt)}`;
    } else if (isExpired) {
        topStatusText = `Подписка закончилась ${formatDate(expiresAt)}`;
    }

    return (
        <div className="p-4 pb-24 space-y-6">
            {/* Top Status Bar */}
            <div className="text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                {topStatusText}
            </div>

            <div className="text-center space-y-2">
                <h1 className="text-2xl font-bold">{headerTitle}</h1>
                <p className="text-gray-500">{headerSubtitle}</p>
            </div>

            <div className="space-y-4">
                {PLANS.map((plan) => {
                    let isCurrent = false;
                    let customButtonText: string | undefined;
                    let disabled = false;
                    let bottomContent: React.ReactNode | undefined;

                    if (subscription) {
                        // Map new subscription format to old plan codes for compatibility
                        const userPlanCode = subscription.plan === 'free' ? 'FREE' :
                                             subscription.plan === 'pro' ? 'MONTHLY' : 'FREE'; // Default to MONTHLY for pro

                        // FREE CARD
                        if (plan.id === 'free') {
                            if (userPlanCode === 'FREE') {
                                isCurrent = true;
                                customButtonText = "Базовый бесплатный тариф";
                                disabled = true; // Always disabled if current
                            } else {
                                // User is PRO
                                customButtonText = "Базовый бесплатный тариф";
                                disabled = true;
                            }
                        }
                        // PRO CARDS
                        else {
                            const planCode = plan.id === 'pro_monthly' ? 'MONTHLY' : 'YEARLY';

                            // If this specific PRO plan is active
                            if (userPlanCode === planCode) {
                                isCurrent = true;

                                // State B: Active Pro - Use new subscription format
                                const autoRenew = subscription.autorenew_enabled;
                                const paymentMethod = subscription.payment_method;
                                const hasCard = paymentMethod?.is_attached ?? false;

                                bottomContent = (
                                    <div className="space-y-3">
                                        {/* Expiration Badge */}
                                        <div className="bg-white/10 rounded-lg p-3 text-center">
                                            <p className="text-sm font-medium text-white">
                                                Текущий план до {formatDate(expiresAt)}
                                            </p>
                                        </div>

                                        {/* Auto-renew Status */}
                                        <div className="space-y-2">
                                            {hasCard && autoRenew ? (
                                                // Variant 1: Auto-renew ON
                                                <>
                                                    <div className="flex items-center justify-center gap-2 text-sm text-green-400">
                                                        <span>🔄</span>
                                                        <span>Автопродление включено</span>
                                                    </div>
                                                    <p className="text-xs text-center text-gray-400">
                                                        {paymentMethod.card_mask || 'Карта ••••'}
                                                    </p>
                                                    <button
                                                        onClick={() => navigate('/settings')}
                                                        className="w-full text-center text-sm text-gray-300 hover:text-white underline decoration-gray-500 hover:decoration-white transition-all"
                                                    >
                                                        Управлять автопродлением
                                                    </button>
                                                </>
                                            ) : hasCard && !autoRenew ? (
                                                // Variant 2: Auto-renew OFF
                                                <>
                                                    <div className="flex items-center justify-center gap-2 text-sm text-red-400">
                                                        <span>⛔</span>
                                                        <span>Автопродление выключено</span>
                                                    </div>
                                                    <button
                                                        onClick={handleToggleAutoRenew}
                                                        disabled={togglingAutoRenew}
                                                        className="w-full py-2 bg-white text-black rounded-lg text-sm font-bold hover:bg-gray-100 transition-colors flex items-center justify-center gap-2"
                                                    >
                                                        {togglingAutoRenew && <Loader2 className="animate-spin" size={14} />}
                                                        Включить автопродление
                                                    </button>
                                                </>
                                            ) : (
                                                // Variant 3: No Card
                                                <>
                                                    <div className="flex items-center justify-center gap-2 text-sm text-yellow-500">
                                                        <span>❗</span>
                                                        <span>Автопродление недоступно</span>
                                                    </div>
                                                    <p className="text-xs text-center text-gray-400">
                                                        Привяжите карту
                                                    </p>
                                                    <button
                                                        onClick={handleAddCard}
                                                        disabled={togglingAutoRenew}
                                                        className="w-full py-2 bg-white text-black rounded-lg text-sm font-bold hover:bg-gray-100 transition-colors flex items-center justify-center gap-2"
                                                    >
                                                        {togglingAutoRenew && <Loader2 className="animate-spin" size={14} />}
                                                        Добавить карту
                                                    </button>
                                                </>
                                            )}
                                        </div>
                                    </div>
                                );
                            }
                            // If User is PRO but on DIFFERENT plan (e.g. Monthly vs Yearly)
                            else if (isPro) {
                                // Disable other pro plans while one is active?
                                // User request: "Если план Pro уже активен... Кнопку отключить"
                                // It seems they want to lock it down.
                                disabled = true;
                                customButtonText = "У вас уже активен PRO";
                            }
                            // State C: Expired Pro (User is Free now, but was Pro)
                            else if (isExpired) {
                                // Show "Return PRO" button
                                // Logic: Standard button but with specific text?
                                // Request: "Большая CTA-кнопка: «Вернуть PRO за 299 ₽ / месяц»"
                                // Also "Плашка с текстом: Доступ к PRO закончился..."

                                // We can use bottomContent here too to add the badge above the button
                                bottomContent = (
                                    <div className="space-y-3">
                                        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-center">
                                            <p className="text-sm font-medium text-red-400">
                                                Доступ к PRO закончился {formatDate(expiresAt)}
                                            </p>
                                        </div>
                                        <button
                                            onClick={() => handleSelectPlan(plan.id)}
                                            disabled={loadingPlanId === plan.id}
                                            className="w-full py-3 bg-white text-black rounded-xl font-bold hover:bg-gray-100 transition-all flex items-center justify-center gap-2"
                                        >
                                            {loadingPlanId === plan.id ? (
                                                <span className="animate-pulse">Загрузка...</span>
                                            ) : (
                                                `Вернуть PRO за ${plan.priceText}`
                                            )}
                                        </button>
                                    </div>
                                );
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
                            bottomContent={bottomContent}
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
