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

    // Premium Styles based on plan type
    const cardClasses = isFree
        ? "bg-white text-slate-900 border border-slate-200 shadow-sm"
        : "bg-gradient-to-b from-slate-800 to-slate-950 text-white border border-slate-700/50 shadow-2xl shadow-slate-900/20";

    const badgeClasses = isYearly
        ? "bg-amber-400 text-amber-950 shadow-sm"
        : "bg-slate-700 text-slate-200";

    return (
        <div className={`relative rounded-2xl p-5 overflow-hidden flex flex-col transition-all duration-300 ring-1 ring-black/5 ${cardClasses}`}>
            {/* Tag Badge */}
            {plan.tag && (
                <div className={`absolute top-0 right-0 px-3 py-1 rounded-bl-xl text-[10px] font-black tracking-widest uppercase z-10 ${badgeClasses}`}>
                    {plan.tag}
                </div>
            )}

            {/* Header section */}
            <div className="mb-5">
                <div className="flex justify-between items-start mb-1">
                    <h3 className={`text-[10px] font-bold uppercase tracking-[0.15em] ${isFree ? 'text-slate-400' : 'text-slate-500'}`}>
                        {isFree ? 'Лимитированный доступ' : 'Премиум функции'}
                    </h3>
                </div>

                <div className="flex items-end justify-between gap-2">
                    <div className="flex flex-col">
                        <h2 className="text-xl font-extrabold tracking-tight mb-0.5">{plan.name}</h2>
                        {isFree && (
                            <p className="text-[11px] font-medium text-slate-500">
                                3 фото/день · 7 дней истории
                            </p>
                        )}
                        {!isFree && (
                            <p className={`text-[11px] font-bold uppercase tracking-wider ${isYearly ? 'text-amber-400' : 'text-slate-400'}`}>
                                {isYearly ? 'Максимальная выгода' : 'Полный безлимит'}
                            </p>
                        )}
                    </div>

                    {/* Price Section with better separation */}
                    <div className="flex flex-col items-end relative">
                        {/* Subtle glow for PRO price */}
                        {!isFree && <div className="absolute inset-0 bg-white/5 blur-xl -z-10" />}

                        <div className="flex items-baseline gap-1.5">
                            {plan.oldPriceText && (
                                <span className={`text-[11px] font-medium line-through decoration-1 ${isFree ? 'text-slate-300' : 'text-slate-600'}`}>
                                    {plan.oldPriceText}
                                </span>
                            )}
                            <span className={`text-2xl font-black tabular-nums tracking-tighter ${!isFree ? 'text-white drop-shadow-sm' : 'text-slate-900'}`}>
                                {plan.priceText.split(' ')[0]}
                                <small className="text-xs font-bold ml-0.5 opacity-80 uppercase">{plan.priceText.split(' ').slice(1).join(' ')}</small>
                            </span>
                        </div>
                        {plan.priceSubtext && (
                            <p className={`text-[10px] font-bold uppercase tracking-widest mt-0.5 ${isFree ? 'text-slate-400' : 'text-slate-500'}`}>
                                {plan.priceSubtext}
                            </p>
                        )}
                    </div>
                </div>
            </div>

            {/* Features list - emphasized for PRO */}
            <div className={`mb-6 p-4 rounded-xl flex-grow ${isFree ? 'bg-slate-50/50' : 'bg-white/5 border border-white/5'}`}>
                <ul className="space-y-3">
                    {plan.features.map((feature, i) => {
                        // Detect if feature starts with an emoji to hide the checkmark
                        const hasEmoji = /^\p{Emoji}/u.test(feature);

                        return (
                            <li key={i} className="flex items-start gap-3">
                                {!hasEmoji && (
                                    <div className={`mt-0.5 shrink-0 w-4 h-4 rounded-full flex items-center justify-center ${isFree ? 'bg-slate-200 text-slate-500' : 'bg-emerald-500/10 text-emerald-400'}`}>
                                        <Check size={10} strokeWidth={4} />
                                    </div>
                                )}
                                <span className={`text-[13px] leading-snug font-medium ${isFree ? 'text-slate-600' : 'text-slate-200'} ${hasEmoji ? 'ml-0' : ''}`}>
                                    {feature}
                                </span>
                            </li>
                        );
                    })}
                </ul>
            </div>

            {/* CTA section */}
            <div className="mt-auto">
                {bottomContent ? (
                    bottomContent
                ) : (
                    <button
                        onClick={() => onSelect(plan.id)}
                        disabled={isCurrent || isLoading || disabled}
                        className={`w-full h-12 rounded-xl font-black text-[13px] uppercase tracking-wider transition-all active:scale-[0.98] flex items-center justify-center gap-2
                            ${disabled
                                ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                                : isCurrent
                                    ? (isFree ? "bg-slate-50 text-slate-300 border border-slate-100" : "bg-white/5 text-white/30 border border-white/5")
                                    : (isFree ? "bg-slate-900 text-white hover:shadow-lg shadow-slate-900/20" : "bg-white text-slate-950 shadow-lg shadow-white/10 hover:bg-slate-50")
                            }
                            ${isLoading ? 'opacity-70 cursor-wait' : ''}
                        `}
                    >
                        {isLoading ? (
                            <div className="flex items-center gap-2">
                                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                <span>Ждем...</span>
                            </div>
                        ) : customButtonText ? (
                            customButtonText
                        ) : isCurrent ? (
                            "Выбрано"
                        ) : (
                            isFree ? "Начать тут" : (isYearly ? "Получить PRO навсегда*" : "Подключить PRO")
                        )}
                    </button>
                )}
            </div>
        </div>
    );
};

export default PlanCard;
