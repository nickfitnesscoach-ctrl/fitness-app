import React from 'react';
import { Check, Loader2 } from 'lucide-react';

export type PlanId = "free" | "pro_monthly" | "pro_yearly";

export interface Plan {
    id: PlanId;
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
}

const PlanCard: React.FC<PlanCardProps> = ({ plan, isCurrent, isLoading, onSelect }) => {
    const isFree = plan.id === 'free';

    // Styles based on plan type
    const cardClasses = isFree
        ? "bg-white text-gray-900 border border-gray-200"
        : "bg-gradient-to-b from-gray-900 to-gray-800 text-white border border-gray-700";

    const buttonClasses = isFree
        ? "bg-gray-100 text-gray-400 cursor-not-allowed" // Disabled style for current free plan
        : "bg-white text-black hover:bg-gray-100 active:scale-95";

    const activeProButtonClasses = "bg-white text-black hover:bg-gray-100 active:scale-95";
    const disabledButtonClasses = "bg-gray-700 text-gray-400 cursor-not-allowed";

    return (
        <div className={`relative rounded-3xl p-6 shadow-lg overflow-hidden flex flex-col h-full ${cardClasses}`}>
            {/* Badge */}
            {plan.tag && (
                <div className="absolute top-0 right-0 bg-yellow-500 text-black text-xs font-bold px-3 py-1 rounded-bl-xl z-10">
                    {plan.tag}
                </div>
            )}

            {/* Header */}
            <div className="mb-4">
                <h3 className="font-bold text-lg mb-1">{plan.name}</h3>
                <div className="flex items-baseline gap-2 flex-wrap">
                    <span className="text-3xl font-bold">{plan.priceText}</span>
                    {plan.oldPriceText && (
                        <span className="text-gray-400 text-sm line-through decoration-gray-400">
                            {plan.oldPriceText}
                        </span>
                    )}
                </div>
                {plan.priceSubtext && (
                    <p className="text-sm text-gray-400 mt-1">{plan.priceSubtext}</p>
                )}
            </div>

            {/* Features */}
            <ul className="space-y-3 mb-8 flex-grow">
                {plan.features.map((feature, i) => (
                    <li key={i} className="flex items-start gap-3">
                        <div className={`mt-0.5 p-0.5 rounded-full ${isFree ? 'bg-green-100 text-green-600' : 'bg-white/10 text-white'}`}>
                            <Check size={14} />
                        </div>
                        <span className={`text-sm ${isFree ? 'text-gray-600' : 'text-gray-300'}`}>
                            {feature}
                        </span>
                    </li>
                ))}
            </ul>

            {/* Button */}
            <button
                onClick={() => onSelect(plan.id)}
                disabled={isCurrent || isLoading}
                className={`w-full py-3 rounded-xl font-bold transition-all flex items-center justify-center gap-2
                    ${isCurrent
                        ? (isFree ? "bg-gray-100 text-gray-400" : "bg-white/20 text-white/50")
                        : (isFree ? "bg-black text-white hover:bg-gray-800" : "bg-white text-black hover:bg-gray-100")
                    }
                    ${isLoading ? 'opacity-80 cursor-wait' : ''}
                `}
            >
                {isLoading ? (
                    <Loader2 className="animate-spin" size={20} />
                ) : isCurrent ? (
                    "Текущий план"
                ) : (
                    isFree ? "Использовать бесплатно" : (plan.id === 'pro_yearly' ? "Оформить годовую" : "Оформить подписку")
                )}
            </button>
        </div>
    );
};

export default PlanCard;
