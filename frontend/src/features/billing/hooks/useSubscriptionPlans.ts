import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../../services/api';
import type { SubscriptionPlan } from '../../../types/billing';
import type { PlanCode } from '../utils/types';

interface UseSubscriptionPlansResult {
    plans: SubscriptionPlan[];
    loading: boolean;
    error: string | null;
}

/**
 * Как мы хотим видеть тарифы в интерфейсе:
 * сначала бесплатный, потом месячный PRO, потом годовой PRO.
 * Это “бизнес-правило”, чтобы UI всегда был одинаковым.
 */
const ORDER: PlanCode[] = ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'];

function isPlanCode(code: string): code is PlanCode {
    return ORDER.includes(code as PlanCode);
}

function sortByOrder(a: SubscriptionPlan, b: SubscriptionPlan): number {
    // Здесь предполагается, что code уже валидный PlanCode (см. фильтр ниже).
    return ORDER.indexOf(a.code as PlanCode) - ORDER.indexOf(b.code as PlanCode);
}

// DEV-only: мок подгружаем динамически, чтобы он НЕ попадал в prod-bundle
async function loadDevMockPlans(): Promise<SubscriptionPlan[]> {
    const mod = await import('../__mocks__/subscriptionPlans');
    return mod.mockSubscriptionPlans;
}

export const useSubscriptionPlans = (): UseSubscriptionPlansResult => {
    const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    /**
     * Защита от “гонок”:
     * если пользователь ушёл со страницы, мы больше не обновляем состояние.
     */
    const isMountedRef = useRef(true);
    useEffect(() => {
        isMountedRef.current = true;
        return () => {
            isMountedRef.current = false;
        };
    }, []);

    const safeSetState = useCallback(
        (next: { plans?: SubscriptionPlan[]; loading?: boolean; error?: string | null }) => {
            if (!isMountedRef.current) return;
            if (next.plans !== undefined) setPlans(next.plans);
            if (next.loading !== undefined) setLoading(next.loading);
            if (next.error !== undefined) setError(next.error);
        },
        [],
    );

    const load = useCallback(async () => {
        // Старт загрузки: показываем спиннер и сбрасываем старую ошибку
        safeSetState({ loading: true, error: null });

        try {
            // В DEV работаем от моков, чтобы фронтенд можно было развивать без бэка
            const rawPlans = import.meta.env.DEV ? await loadDevMockPlans() : await api.getSubscriptionPlans();

            // Фильтруем “мусор” (пустые/неизвестные коды), чтобы UI не ломался
            const cleaned = (rawPlans || []).filter((p): p is SubscriptionPlan => Boolean(p?.code) && isPlanCode(p.code));

            // Стабильный порядок отображения
            const sorted = [...cleaned].sort(sortByOrder);

            safeSetState({ plans: sorted });
        } catch (e) {
            // В проде лучше логировать централизованно, но console оставляем как fallback
            // eslint-disable-next-line no-console
            console.error('[billing] getSubscriptionPlans error:', e);

            safeSetState({ error: 'Не удалось загрузить тарифы, попробуйте позже' });
        } finally {
            safeSetState({ loading: false });
        }
    }, [safeSetState]);

    useEffect(() => {
        void load();
    }, [load]);

    return { plans, loading, error };
};
    