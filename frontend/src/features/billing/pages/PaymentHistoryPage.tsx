import React from 'react';
import PageHeader from '../../../components/PageHeader';
import PaymentHistoryList from '../components/billing/PaymentHistoryList';
import { usePaymentHistory } from '../hooks/usePaymentHistory';
import { PageContainer } from '../../../components/shared/PageContainer';

const PaymentHistoryPage: React.FC = () => {
    const { payments, loading } = usePaymentHistory(20);

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50">
                <PageHeader title="История оплат" fallbackRoute="/settings/subscription" />
                <div className="p-4 text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto" />
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <PageHeader title="История оплат" fallbackRoute="/settings/subscription" />
            <PageContainer className="py-6 space-y-[var(--section-gap)]">
                <PaymentHistoryList payments={payments} />
            </PageContainer>
        </div>
    );
};

export default PaymentHistoryPage;
