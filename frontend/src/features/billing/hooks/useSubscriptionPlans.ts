import { useState, useEffect } from 'react';
import type { SubscriptionPlan } from '../../../types/billing';
import type { PlanCode } from '../utils/types';
import { api } from '../../../services/api';

interface UseSubscriptionPlansResult {
    plans: SubscriptionPlan[];
    loading: boolean;
    error: string | null;
}

const ORDER: PlanCode[] = ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'];

/**
 * Type guard to filter valid plan codes from API response
 */
function isPlanCode(code: string): code is PlanCode {
    return ORDER.includes(code as PlanCode);
}

export const useSubscriptionPlans = (): UseSubscriptionPlansResult => {
    const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchPlans = async () => {
            try {
                setLoading(true);

                const apiPlans = await api.getSubscriptionPlans();

                const sortedPlans = apiPlans
                    .filter(p => isPlanCode(p.code))
                    .sort((a, b) => ORDER.indexOf(a.code as PlanCode) - ORDER.indexOf(b.code as PlanCode));

                setPlans(sortedPlans);
            } catch (e) {
                console.error(e);
                setError('Не удалось загрузить тарифы, попробуйте позже');
            } finally {
                setLoading(false);
            }
        };
        fetchPlans();
    }, []);

    return { plans, loading, error };
};
