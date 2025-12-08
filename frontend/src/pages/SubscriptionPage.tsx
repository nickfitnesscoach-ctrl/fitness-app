import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import PlanCard, { Plan, PlanId } from '../components/PlanCard';
import { api } from '../services/api';
import { useBilling } from '../contexts/BillingContext';
import { useAuth } from '../contexts/AuthContext';
import { Loader2 } from 'lucide-react';
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';



const SubscriptionPage: React.FC = () => {
    const billing = useBilling();
    const navigate = useNavigate();
    const { isBrowserDebug } = useAuth();
    const { isReady, isTelegramWebApp: webAppDetected, isBrowserDebug: webAppBrowserDebug } = useTelegramWebApp();
    const [loadingPlanId, setLoadingPlanId] = useState<PlanId | null>(null);
    const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);
    const [plans, setPlans] = useState<Plan[]>([]);
    const [loadingPlans, setLoadingPlans] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchPlans = async () => {
            try {
                setLoadingPlans(true);

                // DEV MODE: Mock subscription plans for testing UI
                const isDev = import.meta.env.DEV;
                const mockApiPlans = [
                    {
                        code: 'FREE',
                        display_name: 'Базовый',
                        price: 0,
                        old_price: null,
                        is_popular: false,
                        features: [
                            '3 анализа еды в день',
                            'Базовая статистика',
                            'Дневник питания'
                        ]
                    },
                    {
                        code: 'PRO_MONTHLY',
                        display_name: 'PRO месяц',
                        price: 299,
                        old_price: 499,
                        is_popular: true,
                        features: [
                            'Безлимитные анализы еды',
                            'Персональные рекомендации',
                            'Подробная статистика',
                            'Приоритетная поддержка'
                        ]
                    },
                    {
                        code: 'PRO_YEARLY',
                        display_name: 'PRO год',
                        price: 2990,
                        old_price: 4990,
                        is_popular: false,
                        features: [
                            'Все возможности PRO',
                            'Экономия 17%',
                            'Безлимитные анализы еды',
                            'Персональные рекомендации'
                        ]
                    }
                ];

                const apiPlans = isDev ? mockApiPlans : await api.getSubscriptionPlans();
                const uiPlans: Plan[] = apiPlans
                    .filter(p => ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'].includes(p.code))
                    .map(p => {
                        let id = p.code.toLowerCase();
                        if (p.code === 'PRO_MONTHLY') id = 'pro_monthly';
                        if (p.code === 'PRO_YEARLY') id = 'pro_yearly';
                        if (p.code === 'FREE') id = 'free';

                        let priceText = `${p.price} ₽`;
                        if (p.code === 'PRO_MONTHLY') priceText = `${p.price} ₽ / месяц`;
                        if (p.code === 'PRO_YEARLY') priceText = `${p.price} ₽ / год`;
                        if (p.code === 'FREE') priceText = '0 ₽';

                        return {
                            id,
                            code: p.code,
                            name: p.display_name,
                            priceText,
                            features: p.features || [],
                            oldPriceText: p.old_price ? `${p.old_price} ₽` : undefined,
                            tag: p.is_popular ? 'POPULAR' : undefined,
                            priceSubtext: p.code === 'PRO_YEARLY' ? `≈ ${Math.round(p.price / 12)} ₽ / месяц` : undefined
                        };
                    });

                // Sort: Free, Monthly, Yearly
                const order = ['free', 'pro_monthly', 'pro_yearly'];
                uiPlans.sort((a, b) => {
                    const idxA = order.indexOf(a.id);
                    const idxB = order.indexOf(b.id);
                    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
                    if (idxA !== -1) return -1;
                    if (idxB !== -1) return 1;
                    return 0;
                });

                setPlans(uiPlans);
            } catch (e) {
                console.error(e);
                setError('Не удалось загрузить тарифы, попробуйте позже');
            } finally {
                setLoadingPlans(false);
            }
        };
        fetchPlans();
    }, []);

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

        // Block payments in Browser Debug Mode
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
    let headerSubtitle = "Получи максимум от EatFit24";
    let topStatusText = "Текущий тариф: Free";

    if (isPro) {
        topStatusText = `Текущий тариф: PRO до ${formatDate(expiresAt)}`;
    } else if (isExpired) {
        topStatusText = `Подписка закончилась ${formatDate(expiresAt)}`;
    }

    // While WebApp is initializing
    if (!isReady) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    // WebApp is ready but we're not in Telegram
    // Allow Browser Debug Mode to continue (but payments will be disabled)
    if (!webAppDetected && !isBrowserDebug && !webAppBrowserDebug) {
        return (
            <div className="min-h-screen flex items-center justify-center p-4">
                <div className="bg-orange-50 border-2 border-orange-200 rounded-2xl p-6 text-center max-w-md">
                    <h2 className="text-xl font-bold text-orange-900 mb-2">
                        Откройте через Telegram
                    </h2>
                    <p className="text-orange-700">
                        Это приложение работает только внутри Telegram.
                        Пожалуйста, откройте бота и нажмите кнопку "Открыть приложение".
                    </p>
                </div>
            </div>
        );
    }

    return (
        <div className="px-4 py-6 max-w-2xl mx-auto">
            <div className="px-4 pt-2 pb-3 text-center mb-6">
                <p className="text-[11px] font-medium tracking-[0.18em] uppercase text-slate-500">
                    {topStatusText}
                </p>

                <h1 className="mt-1 text-[22px] font-bold leading-tight text-slate-900">
                    {headerTitle}
                </h1>

                <p className="mt-2 text-sm leading-snug text-slate-600">
                    {headerSubtitle}
                </p>
            </div>

            <div className="space-y-4">
                {loadingPlans ? (
                    <div className="flex justify-center py-12">
                        <Loader2 className="animate-spin text-blue-500" size={40} />
                    </div>
                ) : error ? (
                    <div className="text-center text-red-500 py-8 bg-red-50 rounded-xl">
                        {error}
                    </div>
                ) : plans.map((plan) => {
                    let isCurrent = false;
                    let customButtonText: string | undefined;
                    let disabled = false;
                    let bottomContent: React.ReactNode | undefined;

                    if (subscription) {
                        // Map new subscription format to old plan codes for compatibility
                        const userPlanCode = billing.billingMe?.plan_code ||
                            (subscription.plan === 'free' ? 'FREE' : 'MONTHLY');

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
                                    <div className="space-y-3 mt-auto">
                                        {/* Expiration Badge */}
                                        <div className="bg-white/10 rounded-lg p-3 text-center">
                                            <p className="text-sm font-medium text-white">
                                                Текущий план до {formatDate(expiresAt)}
                                            </p>
                                        </div>

                                        {/* Auto-renew Status */}
                                        <div className="space-y-2.5">
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
                                    <div className="space-y-3 mt-auto">
                                        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-center">
                                            <p className="text-sm font-medium text-red-400">
                                                Доступ к PRO закончился {formatDate(expiresAt)}
                                            </p>
                                        </div>
                                        <button
                                            onClick={() => handleSelectPlan(plan.id)}
                                            disabled={loadingPlanId === plan.id}
                                            className="w-full py-3.5 bg-white text-black rounded-xl font-bold hover:bg-gray-100 transition-all flex items-center justify-center gap-2"
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

            <p className="text-center text-xs text-gray-400 mt-4">
                Нажимая кнопку, вы соглашаетесь с условиями использования и политикой конфиденциальности.
            </p>
        </div>
    );
};

export default SubscriptionPage;
