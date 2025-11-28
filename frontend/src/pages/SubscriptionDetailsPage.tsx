import React, { useState } from 'react';
import { useBilling } from '../contexts/BillingContext';
import { ChevronRight, CreditCard, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const SubscriptionDetailsPage: React.FC = () => {
    const billing = useBilling();
    const navigate = useNavigate();
    const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);

    const showToast = (message: string) => {
        const tg = window.Telegram?.WebApp;
        if (tg?.showAlert) {
            tg.showAlert(message);
        } else {
            alert(message);
        }
    };

    const subscription = billing.subscription;

    // Проверки
    const isPro = subscription?.plan === 'pro';
    const expiresAt = subscription?.expires_at ?? null;
    const autoRenewEnabled = subscription?.autorenew_enabled ?? false;
    const autoRenewAvailable = subscription?.autorenew_available ?? false;
    const paymentMethod = subscription?.payment_method;
    const hasCard = paymentMethod?.is_attached ?? false;

    const handleToggleAutoRenew = async () => {
        if (togglingAutoRenew) return;

        if (!autoRenewAvailable) {
            showToast("Привяжите карту для включения автопродления");
            return;
        }

        try {
            setTogglingAutoRenew(true);
            await billing.setAutoRenew(!autoRenewEnabled);
            showToast(autoRenewEnabled ? "Автопродление отключено" : "Автопродление включено");
        } catch (error: any) {
            const message = error?.message || "Не удалось изменить настройки";
            showToast(message);
        } finally {
            setTogglingAutoRenew(false);
        }
    };

    const handlePaymentMethodClick = async () => {
        if (!hasCard) {
            try {
                await billing.addPaymentMethod();
            } catch (error) {
                showToast("Ошибка при запуске привязки карты");
            }
        } else {
            showToast("Смена карты будет доступна позже");
        }
    };

    const formatDate = (dateString: string | null) => {
        if (!dateString) return '';
        return new Date(dateString).toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'numeric',
            year: 'numeric'
        });
    };

    const renderCardInfo = () => {
        if (!hasCard || !paymentMethod) {
            return <span>Карта не привязана</span>;
        }

        return (
            <>
                <CreditCard size={14} />
                <span>{paymentMethod.card_mask} · {paymentMethod.card_brand || 'Card'}</span>
            </>
        );
    };

    return (
        <div className="min-h-screen bg-gray-50 pb-24">
            {/* Header */}
            <div className="bg-white px-4 py-3 flex items-center gap-3 shadow-sm sticky top-0 z-10">
                <button
                    onClick={() => navigate(-1)}
                    className="p-2 -ml-2 text-gray-600 hover:bg-gray-100 rounded-full transition-colors"
                >
                    <ArrowLeft size={24} />
                </button>
                <h1 className="text-xl font-bold text-gray-900">Подписка и оплата</h1>
            </div>

            <div className="p-4 space-y-6">
                <div className="bg-white rounded-2xl overflow-hidden shadow-sm">
                    {/* Tariff Status */}
                    <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                        <span className="text-gray-900">Тариф</span>
                        <span className="text-gray-500 font-medium">
                            {isPro ? `PRO до ${formatDate(expiresAt)}` : 'Free'}
                        </span>
                    </div>

                    {/* Auto-renew Toggle */}
                    <div className="p-4 border-b border-gray-100 space-y-2">
                        <div className="flex justify-between items-center">
                            <span className="text-gray-900">Автопродление PRO</span>
                            <button
                                onClick={handleToggleAutoRenew}
                                disabled={togglingAutoRenew || !autoRenewAvailable}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 ${autoRenewEnabled ? 'bg-green-500' : 'bg-gray-200'
                                    } ${(!autoRenewAvailable || togglingAutoRenew) ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                <span
                                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${autoRenewEnabled ? 'translate-x-6' : 'translate-x-1'
                                        }`}
                                />
                            </button>
                        </div>
                        <p className="text-xs text-gray-400 leading-relaxed">
                            {autoRenewAvailable ? (
                                autoRenewEnabled
                                    ? "Ежемесячное списание через привязанную карту."
                                    : "Списание не выполняется. Доступ к PRO сохранится до конца оплаченного периода."
                            ) : (
                                "Автопродление недоступно — привяжите карту в разделе «Способ оплаты»."
                            )}
                        </p>
                    </div>

                    {/* Payment Method */}
                    <div
                        onClick={handlePaymentMethodClick}
                        className="p-4 flex justify-between items-center active:bg-gray-50 cursor-pointer transition-colors"
                    >
                        <div className="space-y-1">
                            <span className="text-gray-900 block">Способ оплаты</span>
                            <div className="flex items-center gap-2 text-sm text-gray-500">
                                {renderCardInfo()}
                            </div>
                        </div>
                        <ChevronRight size={20} className="text-gray-300" />
                    </div>

                    {/* Payment History */}
                    <div
                        onClick={() => navigate('/settings/history')}
                        className="p-4 flex justify-between items-center active:bg-gray-50 cursor-pointer transition-colors"
                    >
                        <span className="text-gray-900">История оплат</span>
                        <ChevronRight size={20} className="text-gray-300" />
                    </div>
                </div>
            </div>
        </div>
    );
};

export default SubscriptionDetailsPage;
