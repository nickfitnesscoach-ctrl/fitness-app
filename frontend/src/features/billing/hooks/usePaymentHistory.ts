import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../../../services/api';
import type { PaymentHistoryItem } from '../../../types/billing';

interface UsePaymentHistoryResult {
    payments: PaymentHistoryItem[];
    loading: boolean;
    error: string | null;
    /**
     * Перезагрузить историю.
     * Можно передать другой лимит (например, “показать больше”).
     */
    reload: (limit?: number) => Promise<void>;
}

/**
 * Хук загружает историю оплат пользователя.
 * Важно:
 * - защищаемся от гонок (когда два запроса идут параллельно)
 * - не обновляем state после ухода со страницы
 */
export const usePaymentHistory = (initialLimit = 20): UsePaymentHistoryResult => {
    const [payments, setPayments] = useState<PaymentHistoryItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // “Жив ли компонент?” — чтобы не обновлять state после размонтирования
    const mountedRef = useRef(false);

    // Версия запроса: если запустили новый reload, старый результат игнорируем
    const requestIdRef = useRef(0);

    const loadPayments = useCallback(
        async (limit = initialLimit) => {
            requestIdRef.current += 1;
            const myRequestId = requestIdRef.current;

            setLoading(true);
            setError(null);

            try {
                const { results } = await api.getPaymentsHistory(limit);

                // Если компонент уже ушёл или это не самый свежий запрос — ничего не делаем
                if (!mountedRef.current) return;
                if (requestIdRef.current !== myRequestId) return;

                setPayments(results);
            } catch (err) {
                // eslint-disable-next-line no-console
                console.error('[billing] Failed to load payments:', err);

                if (!mountedRef.current) return;
                if (requestIdRef.current !== myRequestId) return;

                setError('Не удалось загрузить историю оплат');
            } finally {
                if (!mountedRef.current) return;
                if (requestIdRef.current !== myRequestId) return;

                setLoading(false);
            }
        },
        [initialLimit],
    );

    useEffect(() => {
        mountedRef.current = true;
        void loadPayments();

        return () => {
            mountedRef.current = false;
        };
    }, [loadPayments]);

    return { payments, loading, error, reload: loadPayments };
};
