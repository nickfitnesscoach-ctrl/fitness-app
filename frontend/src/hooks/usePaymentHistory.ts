import { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import { PaymentHistoryItem } from '../types/billing';

export const usePaymentHistory = (initialLimit = 20) => {
  const [payments, setPayments] = useState<PaymentHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadPayments = useCallback(async (limit = initialLimit) => {
    try {
      setLoading(true);
      setError(null);
      const { results } = await api.getPaymentsHistory(limit);
      setPayments(results);
    } catch (err) {
      console.error('Failed to load payments:', err);
      setError('Не удалось загрузить историю оплат');
    } finally {
      setLoading(false);
    }
  }, [initialLimit]);

  useEffect(() => {
    loadPayments();
  }, [loadPayments]);

  return { payments, loading, error, reload: loadPayments };
};
