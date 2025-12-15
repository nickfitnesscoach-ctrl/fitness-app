import React from 'react';
import { PaymentHistoryItem } from '../../types/billing';
import { PAYMENT_STATUS_BADGES } from '../../constants/billing';
import { formatBillingDate } from '../../utils/date';

interface PaymentHistoryListProps {
  payments: PaymentHistoryItem[];
}

const PaymentHistoryList: React.FC<PaymentHistoryListProps> = ({ payments }) => {
  const getStatusBadge = (status: string) => {
    return PAYMENT_STATUS_BADGES[status] || PAYMENT_STATUS_BADGES.pending;
  };

  if (payments.length === 0) {
    return (
      <div className="text-center text-gray-500 py-8">
        Нет платежей
      </div>
    );
  }

  return (
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
                {formatBillingDate(payment.paid_at)}
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
  );
};

export default PaymentHistoryList;
