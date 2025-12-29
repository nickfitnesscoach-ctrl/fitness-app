import { useState, useEffect } from 'react';
import type { SubscriptionPlan } from '../../../types/billing';
import { api } from '../../../services/api';
import { IS_DEV } from '../../../config/env';
import { mockSubscriptionPlans } from '../__mocks__/plans';

interface UseSubscriptionPlansResult {
    plans: SubscriptionPlan[];
    loading: boolean;
    error: string | null;
}

const ORDER: SubscriptionPlan['code'][] = ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'];

export const useSubscriptionPlans = (): UseSubscriptionPlansResult => {
    const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchPlans = async () => {
            try {
                setLoading(true);

                // DEV MODE: Use mock plans from separate file
                const apiPlans = IS_DEV ? mockSubscriptionPlans : await api.getSubscriptionPlans();

                const sortedPlans = apiPlans
                    .filter(p => ORDER.includes(p.code))
                    .sort((a, b) => ORDER.indexOf(a.code) - ORDER.indexOf(b.code));

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
