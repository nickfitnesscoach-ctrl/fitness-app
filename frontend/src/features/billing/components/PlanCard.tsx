// frontend/src/features/billing/components/PlanCard.tsx
//
// План-роутер: выбирает, какую карточку тарифа рендерить по plan.code.
// Важно: здесь нет JSX-логики, кроме switch.
// Поэтому не используем React.FC и не импортируем React как value.
// Если нужен ReactNode — импортируем только тип.

import type { ReactNode } from 'react';
import type { SubscriptionPlan } from '../../../types/billing';
import type { PlanCode } from '../types';

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
  bottomContent?: ReactNode;
}

export default function PlanCard({
  plan,
  isCurrent,
  isLoading,
  onSelect,
  customButtonText,
  disabled,
  bottomContent,
}: PlanCardProps) {
  // Приводим код тарифа к типу, который ожидает фронт (PlanCode)
  const code = plan.code as PlanCode;

  switch (code) {
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
          // Подтекст в стиле "≈ 208 ₽/мес"
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
}
