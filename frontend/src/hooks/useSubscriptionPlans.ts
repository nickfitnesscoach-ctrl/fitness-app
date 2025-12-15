import { useState, useEffect } from 'react';
import { Plan } from '../components/PlanCard';
import { api } from '../services/api';
import { IS_DEV } from '../config/env';

interface UseSubscriptionPlansResult {
    plans: Plan[];
    loading: boolean;
    error: string | null;
}

export const useSubscriptionPlans = (): UseSubscriptionPlansResult => {
    const [plans, setPlans] = useState<Plan[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchPlans = async () => {
            try {
                setLoading(true);

                // DEV MODE: Mock subscription plans for testing UI
                const mockApiPlans = [
                    {
                        code: 'FREE',
                        display_name: 'Базовый',
                        price: 0,
                        old_price: null,
                        is_popular: false,
                        features: [
                            '3 анализа еды в день',
                            'Базовая статистика',
                            'Дневник питания'
                        ]
                    },
                    {
                        code: 'PRO_MONTHLY',
                        display_name: 'PRO месяц',
                        price: 299,
                        old_price: 499,
                        is_popular: true,
                        features: [
                            'Безлимитные анализы еды',
                            'Персональные рекомендации',
                            'Подробная статистика',
                            'Приоритетная поддержка'
                        ]
                    },
                    {
                        code: 'PRO_YEARLY',
                        display_name: 'PRO год',
                        price: 2990,
                        old_price: 4990,
                        is_popular: false,
                        features: [
                            'Все возможности PRO',
                            'Экономия 17%',
                            'Безлимитные анализы еды',
                            'Персональные рекомендации'
                        ]
                    }
                ];

                const apiPlans = IS_DEV ? mockApiPlans : await api.getSubscriptionPlans();
                const uiPlans: Plan[] = apiPlans
                    .filter(p => ['FREE', 'PRO_MONTHLY', 'PRO_YEARLY'].includes(p.code))
                    .map(p => {
                        let id = p.code.toLowerCase();
                        if (p.code === 'PRO_MONTHLY') id = 'pro_monthly';
                        if (p.code === 'PRO_YEARLY') id = 'pro_yearly';
                        if (p.code === 'FREE') id = 'free';

                        let priceText = `${p.price} ₽`;
                        if (p.code === 'PRO_MONTHLY') priceText = `${p.price} ₽ / месяц`;
                        if (p.code === 'PRO_YEARLY') priceText = `${p.price} ₽ / год`;
                        if (p.code === 'FREE') priceText = '0 ₽';

                        return {
                            id,
                            code: p.code,
                            name: p.display_name,
                            priceText,
                            features: p.features || [],
                            oldPriceText: p.old_price ? `${p.old_price} ₽` : undefined,
                            tag: p.is_popular ? 'POPULAR' : undefined,
                            priceSubtext: p.code === 'PRO_YEARLY' ? `≈ ${Math.round(p.price / 12)} ₽ / месяц` : undefined
                        };
                    });

                // Sort: Free, Monthly, Yearly
                const order = ['free', 'pro_monthly', 'pro_yearly'];
                uiPlans.sort((a, b) => {
                    const idxA = order.indexOf(a.id);
                    const idxB = order.indexOf(b.id);
                    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
                    if (idxA !== -1) return -1;
                    if (idxB !== -1) return 1;
                    return 0;
                });

                setPlans(uiPlans);
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
