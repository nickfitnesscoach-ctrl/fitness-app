// frontend/src/features/billing/components/PlanCard.tsx
//
// План-роутер: выбирает, какую карточку тарифа рендерить по plan.code.
// Важно: здесь нет JSX-логики, кроме switch.
// Поэтому не используем React.FC и не импортируем React как value.
// Если нужен ReactNode — импортируем только тип.

import type { ReactNode } from 'react';
import type { SubscriptionPlan } from '../../../types/billing';
import type { PlanCode } from '../types';
import { getPlanCopy } from '../config/planCopy';

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
  // Marketing copy from frontend SSOT
  const copy = getPlanCopy(plan.code);
  // Billing truth (price, old_price) from API
  const code = plan.code as PlanCode;

  switch (code) {
    case 'FREE':
      return (
        <BasicPlanCard
          displayName={copy.displayName}
          price={plan.price}
          features={copy.features}
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
          displayName={copy.displayName}
          price={plan.price}
          features={copy.features}
          ctaText={customButtonText ?? (isCurrent ? 'Выбрано' : 'Попробовать PRO')}
          isCurrent={isCurrent}
          isLoading={isLoading}
          disabled={disabled}
          onSelect={() => onSelect('PRO_MONTHLY')}
          bottomContent={bottomContent}
        />
      );

    case 'PRO_YEARLY': {
      // old_price: API (DB) is primary, PLAN_COPY.oldPrice is fallback
      const rawOldPrice = plan.old_price ?? copy.oldPrice;
      // Convert to number to handle potential string from DRF DecimalField
      const priceValue = typeof plan.price === 'string' ? Number(plan.price) : plan.price;
      // Only show old_price if it's greater than current price (valid discount)
      const validOldPrice = rawOldPrice && rawOldPrice > priceValue ? rawOldPrice : undefined;

      return (
        <PremiumProCard
          displayName={copy.displayName}
          price={priceValue}
          oldPrice={validOldPrice}
          priceSubtext={`≈ ${Math.round(priceValue / 12)} ₽/мес`}
          features={copy.features}
          ctaText={customButtonText ?? (isCurrent ? 'Выбрано' : 'Забрать план+ PRO')}
          isCurrent={isCurrent}
          isLoading={isLoading}
          disabled={disabled}
          onSelect={() => onSelect('PRO_YEARLY')}
          bottomContent={bottomContent}
        />
      );
    }

    default:
      // Unknown plan code: render with fallback copy
      return (
        <BasicPlanCard
          displayName={copy.displayName}
          price={plan.price}
          features={copy.features}
          ctaText={customButtonText ?? (isCurrent ? 'Ваш текущий тариф' : 'Выбрать')}
          isCurrent={isCurrent}
          isLoading={isLoading}
          disabled={disabled}
          onSelect={() => onSelect(plan.code as PlanCode)}
        />
      );
  }
}
