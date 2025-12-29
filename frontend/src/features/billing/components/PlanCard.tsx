import React from 'react';
import { Check } from 'lucide-react';

export type PlanId = string;

export interface Plan {
    id: PlanId;
    code: string; // Real API code
    name: string;
    priceText: string;
    oldPriceText?: string;
    priceSubtext?: string;
    tag?: string;
    features: string[];
    isPopular?: boolean;
}

interface PlanCardProps {
    plan: Plan;
    isCurrent: boolean;
    isLoading: boolean;
    onSelect: (planId: PlanId) => void;
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
    bottomContent
}) => {
    const isFree = plan.id === 'free';
    const isYearly = plan.id === 'pro_yearly';

    // Styles based on plan type
    const cardClasses = isFree
        ? "bg-white text-gray-900 border border-gray-200 shadow-sm"
        : "bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 text-white border border-slate-700 shadow-xl shadow-slate-200/50";

    const badgeClasses = isYearly
        ? "bg-amber-400 text-amber-950 shadow-sm"
        : "bg-slate-700 text-slate-100";

    return (
        <div className={`relative rounded-2xl p-5 overflow-hidden flex flex-col transition-all duration-300 ${cardClasses}`}>
            {/* Tag Badge */}
            {plan.tag && (
                <div className={`absolute top-0 right-0 px-3 py-1 rounded-bl-xl text-[10px] font-black tracking-widest uppercase z-10 ${badgeClasses}`}>
                    {plan.tag}
                </div>
            )}

            {/* Header section */}
            <div className="mb-4">
                <h3 className={`text-xs font-bold uppercase tracking-[0.1em] mb-1 ${isFree ? 'text-slate-400' : 'text-slate-400'}`}>
                    {isFree ? 'Базовый тариф' : 'Премиум доступ'}
                </h3>
                <div className="flex items-baseline justify-between gap-2">
                    <h2 className="text-xl font-black tracking-tight">{plan.name}</h2>
                    <div className="flex flex-col items-end">
                        <div className="flex items-baseline gap-1.5">
                            {plan.oldPriceText && (
                                <span className={`text-xs line-through decoration-1 ${isFree ? 'text-slate-300' : 'text-slate-500'}`}>
                                    {plan.oldPriceText}
                                </span>
                            )}
                            <span className="text-2xl font-black tabular-nums tracking-tighter">
                                {plan.priceText.split(' ')[0]}
                                <small className="text-sm font-medium ml-0.5">{plan.priceText.split(' ').slice(1).join(' ')}</small>
                            </span>
                        </div>
                        {plan.priceSubtext && (
                            <p className={`text-[10px] font-medium uppercase tracking-wider ${isFree ? 'text-slate-400' : 'text-amber-400/80'}`}>
                                {plan.priceSubtext}
                            </p>
                        )}
                    </div>
                </div>
            </div>

            {/* Features list */}
            <ul className="space-y-2.5 mb-6 flex-grow">
                {plan.features.map((feature, i) => (
                    <li key={i} className="flex items-start gap-2.5">
                        <div className={`mt-0.5 shrink-0 w-4 h-4 rounded-full flex items-center justify-center ${isFree ? 'bg-slate-100 text-slate-500' : 'bg-emerald-500/20 text-emerald-400'}`}>
                            <Check size={10} strokeWidth={4} />
                        </div>
                        <span className={`text-[13px] leading-tight font-medium ${isFree ? 'text-slate-600' : 'text-slate-300'}`}>
                            {feature}
                        </span>
                    </li>
                ))}
            </ul>

            {/* CTA section */}
            <div className="mt-auto">
                {bottomContent ? (
                    bottomContent
                ) : (
                    <button
                        onClick={() => onSelect(plan.id)}
                        disabled={isCurrent || isLoading || disabled}
                        className={`w-full h-11 rounded-xl font-bold text-sm transition-all active:scale-[0.98] flex items-center justify-center gap-2
                            ${disabled
                                ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                                : isCurrent
                                    ? (isFree ? "bg-slate-50 text-slate-400 border border-slate-100" : "bg-white/10 text-white/50 border border-white/10")
                                    : (isFree ? "bg-slate-900 text-white hover:bg-slate-800" : "bg-white text-slate-900 shadow-lg shadow-white/10 hover:bg-slate-50")
                            }
                            ${isLoading ? 'opacity-70 cursor-wait' : ''}
                        `}
                    >
                        {isLoading ? (
                            <div className="flex items-center gap-2">
                                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                <span>Обработка...</span>
                            </div>
                        ) : customButtonText ? (
                            customButtonText
                        ) : isCurrent ? (
                            "Выбрано"
                        ) : (
                            isFree ? "Текущий план" : (isYearly ? "Попробовать PRO год" : "Подключить PRO")
                        )}
                    </button>
                )}
            </div>
        </div>
    );
};

export default PlanCard;
