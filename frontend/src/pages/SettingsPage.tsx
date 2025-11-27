import React, { useState } from 'react';
import { useBilling } from '../contexts/BillingContext';
import { ChevronRight, CreditCard, Bell, Globe, Clock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const SettingsPage: React.FC = () => {
    const billing = useBilling();
    const navigate = useNavigate();
    const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);

    // Mock settings state
    const [notificationsEnabled, setNotificationsEnabled] = useState(true);

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
            // Show modal or info?
            // User requirement: "пока можно просто показывать модалку «скорее всего позже позволим менять карту»"
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
        <div className="p-4 pb-24 space-y-6 bg-gray-50 min-h-screen">
            <h1 className="text-2xl font-bold px-2">Настройки</h1>

            {/* Subscription & Payment Section */}
            <div className="space-y-2">
                <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider px-2">
                    Подписка и оплата
                </h2>
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

                    {/* Payment History (Placeholder) */}
                    <div
                        onClick={() => navigate('/settings/history')}
                        className="p-4 flex justify-between items-center active:bg-gray-50 cursor-pointer transition-colors"
                    >
                        <span className="text-gray-900">История оплат</span>
                        <ChevronRight size={20} className="text-gray-300" />
                    </div>
                </div>
            </div>

            {/* App Settings Section */}
            <div className="space-y-2">
                <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider px-2">
                    Приложение
                </h2>
                <div className="bg-white rounded-2xl overflow-hidden shadow-sm">
                    {/* Notifications */}
                    <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-blue-50 text-blue-500 rounded-lg">
                                <Bell size={18} />
                            </div>
                            <span className="text-gray-900">Уведомления</span>
                        </div>
                        <button
                            onClick={() => setNotificationsEnabled(!notificationsEnabled)}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${notificationsEnabled ? 'bg-blue-500' : 'bg-gray-200'
                                }`}
                        >
                            <span
                                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${notificationsEnabled ? 'translate-x-6' : 'translate-x-1'
                                    }`}
                            />
                        </button>
                    </div>

                    {/* Language */}
                    <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-purple-50 text-purple-500 rounded-lg">
                                <Globe size={18} />
                            </div>
                            <span className="text-gray-900">Язык</span>
                        </div>
                        <span className="text-gray-500 text-sm">Русский</span>
                    </div>

                    {/* Timezone */}
                    <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-orange-50 text-orange-500 rounded-lg">
                                <Clock size={18} />
                            </div>
                            <span className="text-gray-900">Часовой пояс</span>
                        </div>
                        <span className="text-gray-500 text-sm">GMT+3</span>
                    </div>

                    {/* Units (Optional) */}
                    <div className="p-4 flex justify-between items-center">
                        <div className="flex items-center gap-3">
                            <div className="p-2 bg-green-50 text-green-500 rounded-lg">
                                <span className="text-xs font-bold">KG</span>
                            </div>
                            <span className="text-gray-900">Единицы измерения</span>
                        </div>
                        <span className="text-gray-500 text-sm">Вес: кг, Рост: см</span>
                    </div>
                </div>
            </div>

            <div className="text-center text-xs text-gray-400 pt-4">
                Version 1.0.0
            </div>
        </div>
    );
};

export default SettingsPage;
