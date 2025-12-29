import React from 'react';
import { ChevronRight, CreditCard } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../../../components/PageHeader';
import AdminTestPaymentCard from '../components/billing/AdminTestPaymentCard';
import { useSubscriptionDetails } from '../hooks/useSubscriptionDetails';
import { PageContainer } from '../../../components/shared/PageContainer';

const SubscriptionDetailsPage: React.FC = () => {
    const navigate = useNavigate();
    const {
        isPro,
        expiresAtFormatted,
        autoRenewEnabled,
        autoRenewAvailable,
        hasCard,
        cardInfoLabel,
        isAdmin,
        testLivePaymentAvailable,
        togglingAutoRenew,
        creatingTestPayment,
        handleToggleAutoRenew,
        handlePaymentMethodClick,
        handleCreateTestPayment,
    } = useSubscriptionDetails();

    return (
        <div className="min-h-screen bg-gray-50">
            <PageHeader
                title="Подписка и оплата"
                fallbackRoute="/subscription"
            />

            <PageContainer className="py-6 space-y-[var(--section-gap)]">
                <div className="bg-white rounded-[var(--radius-card)] overflow-hidden shadow-sm border border-gray-100">
                    {/* Tariff Status */}
                    <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                        <span className="text-gray-900 font-medium">Тариф</span>
                        <span className="text-gray-500 font-bold tabular-nums">
                            {isPro ? `PRO до ${expiresAtFormatted}` : 'Free'}
                        </span>
                    </div>

                    {/* Auto-renew Toggle */}
                    <div className="p-4 border-b border-gray-100 space-y-2">
                        <div className="flex justify-between items-center">
                            <span className="text-gray-900 font-medium">Автопродление PRO</span>
                            <button
                                onClick={handleToggleAutoRenew}
                                disabled={togglingAutoRenew || !autoRenewAvailable}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${autoRenewEnabled ? 'bg-green-500' : 'bg-gray-200'} ${(!autoRenewAvailable || togglingAutoRenew) ? 'opacity-50 cursor-not-allowed' : ''}`}
                            >
                                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${autoRenewEnabled ? 'translate-x-6' : 'translate-x-1'}`} />
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
                        className="p-4 border-b border-gray-100 flex justify-between items-center active:bg-gray-50 cursor-pointer transition-colors"
                    >
                        <div className="space-y-1">
                            <span className="text-gray-900 font-medium block">Способ оплаты</span>
                            <div className="flex items-center gap-2 text-sm text-gray-500 font-medium">
                                {hasCard && <CreditCard size={14} />}
                                <span className="tabular-nums">{cardInfoLabel}</span>
                            </div>
                        </div>
                        <ChevronRight size={20} className="text-gray-300" />
                    </div>

                    {/* Payment History */}
                    <div
                        onClick={() => navigate('/settings/history')}
                        className="p-4 flex justify-between items-center active:bg-gray-50 cursor-pointer transition-colors"
                    >
                        <span className="text-gray-900 font-medium">История оплат</span>
                        <ChevronRight size={20} className="text-gray-300" />
                    </div>
                </div>

                {/* ADMIN ONLY: Test Live Payment Button */}
                {isAdmin && testLivePaymentAvailable && (
                    <AdminTestPaymentCard
                        creatingTestPayment={creatingTestPayment}
                        onCreateTestPayment={handleCreateTestPayment}
                    />
                )}
            </PageContainer>
        </div>
    );
};

export default SubscriptionDetailsPage;
