import { useEffect, useMemo, useState } from 'react';
import type { SubscriptionPlan } from '../../../types/billing';
import type { PlanCode } from '../utils/types';
import { api } from '../../../services/api';
import { mockSubscriptionPlans } from '../__mocks__/subscriptionPlans';

interface UseSubscriptionPlansResult {
    plans: SubscriptionPlan[];
    loading: boolean;
    error: string | null;
}

const ORDER: PlanCode[] = ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'];

function isPlanCode(code: string): code is PlanCode {
    return ORDER.includes(code as PlanCode);
}

/**
 * Mocks policy:
 * - DEV only: can enable mocks via VITE_BILLING_MOCKS=1 or URL params (?debug=1 / ?mocks=1)
 * - PROD: mocks are NEVER enabled by URL params
 */
function shouldUseMocks(): boolean {
    const isDev = Boolean(import.meta.env.DEV);

    if (import.meta.env.VITE_BILLING_MOCKS === '1') {
        // allow explicit env toggle in any env (you decide), but it's safer to keep only DEV
        return isDev;
    }

    if (isDev && typeof window !== 'undefined') {
        const params = new URLSearchParams(window.location.search);
        return params.get('debug') === '1' || params.get('mocks') === '1';
    }

    return false;
}

export const useSubscriptionPlans = (): UseSubscriptionPlansResult => {
    const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const useMocks = useMemo(() => shouldUseMocks(), []);

    useEffect(() => {
        let cancelled = false;

        const load = async () => {
            setLoading(true);
            setError(null);

            try {
                if (useMocks) {
                    const sortedMocks = [...mockSubscriptionPlans].sort(
                        (a, b) => ORDER.indexOf(a.code as PlanCode) - ORDER.indexOf(b.code as PlanCode),
                    );
                    if (!cancelled) setPlans(sortedMocks);
                    return;
                }

                const apiPlans = await api.getSubscriptionPlans();

                const sortedPlans = (apiPlans || [])
                    .filter((p) => p?.code && isPlanCode(p.code))
                    .sort((a, b) => ORDER.indexOf(a.code as PlanCode) - ORDER.indexOf(b.code as PlanCode));

                if (!cancelled) setPlans(sortedPlans);
            } catch (e) {
                console.error('[billing] getSubscriptionPlans error:', e);
                if (!cancelled) setError('Не удалось загрузить тарифы, попробуйте позже');
            } finally {
                if (!cancelled) setLoading(false);
            }
        };

        load();

        return () => {
            cancelled = true;
        };
    }, [useMocks]);

    return { plans, loading, error };
};
