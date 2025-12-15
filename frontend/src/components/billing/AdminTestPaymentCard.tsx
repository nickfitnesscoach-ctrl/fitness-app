import React from 'react';
import { TestTube } from 'lucide-react';
import { MODE } from '../../config/env';

interface AdminTestPaymentCardProps {
  creatingTestPayment: boolean;
  onCreateTestPayment: () => Promise<void> | void;
}

/**
 * Admin-only component for testing live payments
 * Displays a button to create a 1₽ test payment in production mode
 */
const AdminTestPaymentCard: React.FC<AdminTestPaymentCardProps> = ({
  creatingTestPayment,
  onCreateTestPayment,
}) => {
  return (
    <div className="mt-8 p-4 bg-yellow-50 border border-yellow-200 rounded-2xl">
      <div className="flex items-start gap-3 mb-3">
        <TestTube size={20} className="text-yellow-600 mt-0.5" />
        <div className="flex-1">
          <h3 className="text-sm font-semibold text-yellow-900">
            Тестирование Live-платежей
          </h3>
          <p className="text-xs text-yellow-700 mt-1">
            Проверка боевого магазина YooKassa. Платёж 1₽ на реальную карту.
          </p>
        </div>
      </div>
      <button
        onClick={onCreateTestPayment}
        disabled={creatingTestPayment}
        className="w-full py-2.5 bg-yellow-600 text-white rounded-lg font-medium hover:bg-yellow-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
      >
        {creatingTestPayment ? (
          <>
            <div className="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full" />
            <span>Создание...</span>
          </>
        ) : (
          <>
            <TestTube size={16} />
            <span>Тест: Оплатить 1₽ (live)</span>
          </>
        )}
      </button>
      <p className="text-xs text-yellow-600 mt-2 text-center">
        Доступно только админам • Режим: {MODE}
      </p>
    </div>
  );
};

export default AdminTestPaymentCard;
