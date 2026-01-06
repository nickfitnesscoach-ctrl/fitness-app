// billing/components/PlanCard.tsx
import React from 'react';
import type { SubscriptionPlan } from '../../../types/billing';
import type { PlanCode } from '../utils/types';
import { BasicPlanCard } from './BasicPlanCard';
import { PremiumMonthCard } from './PremiumMonthCard';
import { PremiumProCard } from './PremiumProCard';

interface PlanCardProps {
    plan: SubscriptionPlan;
    isCurrent: boolean;
    isLoading: boolean;
    onSelect: (planCode: PlanCode) => void;
    customButtonText?: string;
    disabled?: boolean;
    bottomContent?: React.ReactNode;
}

const PlanCard: React.FC<PlanCardProps> = ({
    plan,
    isCurrent,
    isLoading,
    onSelect,
    customButtonText,
    disabled,
    bottomContent,
}) => {
    switch (plan.code as PlanCode) {
        case 'FREE':
            return (
                <BasicPlanCard
                    displayName={plan.display_name}
                    price={plan.price}
                    features={plan.features ?? []}
                    ctaText={customButtonText ?? (isCurrent ? 'Ваш текущий тариф' : 'Продолжить бесплатно')}
                    isCurrent={isCurrent}
                    isLoading={isLoading}
                    disabled={disabled}
                    onSelect={() => onSelect('FREE')}
                />
            );

        case 'PRO_MONTHLY':
            return (
                <PremiumMonthCard
                    displayName={plan.display_name}
                    price={plan.price}
                    features={plan.features ?? []}
                    ctaText={customButtonText ?? (isCurrent ? 'Выбрано' : 'Попробовать PRO')}
                    isCurrent={isCurrent}
                    isLoading={isLoading}
                    disabled={disabled}
                    onSelect={() => onSelect('PRO_MONTHLY')}
                    bottomContent={bottomContent}
                />
            );

        case 'PRO_YEARLY':
            return (
                <PremiumProCard
                    displayName={plan.display_name}
                    price={plan.price}
                    oldPrice={plan.old_price}
                    priceSubtext={`≈ ${Math.round(plan.price / 12)} ₽/мес`}
                    features={plan.features ?? []}
                    ctaText={customButtonText ?? (isCurrent ? 'Выбрано' : 'Забрать план+ PRO')}
                    isCurrent={isCurrent}
                    isLoading={isLoading}
                    disabled={disabled}
                    onSelect={() => onSelect('PRO_YEARLY')}
                    bottomContent={bottomContent}
                />
            );

        default:
            return null;
    }
};

export default PlanCard;
