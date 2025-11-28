import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { PaymentHistoryItem } from '../types/billing';

import PageHeader from '../components/PageHeader';

const PaymentHistoryPage: React.FC = () => {
    const [payments, setPayments] = useState<PaymentHistoryItem[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        loadPayments();
    }, []);

    const loadPayments = async () => {
        try {
            setLoading(true);
            const { results } = await api.getPaymentsHistory(20);
            setPayments(results);
        } catch (error) {
            console.error('Failed to load payments:', error);
        } finally {
            setLoading(false);
        }
    };

    const getStatusBadge = (status: string) => {
        const badges = {
            succeeded: 'bg-green-100 text-green-800',
            pending: 'bg-yellow-100 text-yellow-800',
            failed: 'bg-red-100 text-red-800',
            canceled: 'bg-gray-100 text-gray-800',
            refunded: 'bg-blue-100 text-blue-800',
        };
        return badges[status as keyof typeof badges] || badges.pending;
    };

    const formatDate = (dateString: string | null) => {
        if (!dateString) return '—';
        return new Date(dateString).toLocaleDateString('ru-RU', {
            day: 'numeric',
            month: 'short',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

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
        <div className="min-h-screen bg-gray-50 pb-24">
            <PageHeader title="История оплат" fallbackRoute="/settings/subscription" />
            <div className="p-4 space-y-4">

                {payments.length === 0 ? (
                    <div className="text-center text-gray-500 py-8">
                        Нет платежей
                    </div>
                ) : (
                    <div className="space-y-3">
                        {payments.map((payment) => (
                            <div
                                key={payment.id}
                                className="bg-white rounded-xl p-4 shadow-sm"
                            >
                                <div className="flex justify-between items-start mb-2">
                                    <div>
                                        <div className="font-medium">{payment.description}</div>
                                        <div className="text-sm text-gray-500">
                                            {formatDate(payment.paid_at)}
                                        </div>
                                    </div>
                                    <div className="text-right">
                                        <div className="font-bold">
                                            {payment.amount} {payment.currency}
                                        </div>
                                        <span
                                            className={`text-xs px-2 py-1 rounded-full ${getStatusBadge(payment.status)}`}
                                        >
                                            {payment.status}
                                        </span>
                                    </div>
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
};

export default PaymentHistoryPage;
