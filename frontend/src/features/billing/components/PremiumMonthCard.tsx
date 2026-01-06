// billing/components/PremiumMonthCard.tsx
import { PlanPriceStack } from './PlanPriceStack';
import { cleanFeatureText, getPlanFeatureIcon } from '../utils/text';

interface PremiumMonthCardProps {
    displayName: string;
    price: number;
    features: string[];
    ctaText: string;
    isCurrent: boolean;
    isLoading: boolean;
    disabled?: boolean;
    onSelect: () => void;
    bottomContent?: React.ReactNode;
}

export function PremiumMonthCard({
    displayName,
    price,
    features,
    ctaText,
    isCurrent,
    isLoading,
    disabled,
    onSelect,
    bottomContent,
}: PremiumMonthCardProps) {
    const isButtonDisabled = Boolean(disabled || isCurrent || isLoading);

    return (
        <div className="relative w-full">
            {/* Glow */}
            <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/10 via-transparent to-cyan-500/10 blur-3xl -z-10" />

            <div className="relative bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 rounded-3xl shadow-2xl border border-slate-700/50 backdrop-blur-xl flex flex-col h-full p-5 sm:p-8">
                {/* Header */}
                <div className="flex items-start justify-between gap-4 sm:gap-6 mb-5 sm:mb-8">
                    <div className="min-w-0">
                        <p className="text-slate-400 text-[10px] sm:text-xs font-medium tracking-wider uppercase mb-2">
                            Премиум функции
                        </p>
                        <h2 className="text-2xl sm:text-4xl font-extrabold text-white tracking-tight leading-tight">
                            {displayName}
                        </h2>

                        <div className="mt-3 inline-flex items-center bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 px-3 py-1 rounded-full border border-emerald-500/30">
                            <span className="text-emerald-400 text-[10px] sm:text-xs font-bold uppercase tracking-wide">
                                Полный безлимит
                            </span>
                        </div>
                    </div>

                    <PlanPriceStack priceMain={price} priceUnit="₽/мес" alignRight={true} isDark={true} />
                </div>

                {/* Features */}
                <div className="bg-slate-800/50 rounded-2xl backdrop-blur-sm border border-slate-700/30 p-4 sm:p-6 mb-5 sm:mb-6 space-y-3 sm:space-y-4">
                    {features.map((feature, index) => {
                        const cleanText = cleanFeatureText(feature);
                        const icon = getPlanFeatureIcon(cleanText);
                        return (
                            <div key={index} className="flex items-start gap-3">
                                <div className="text-emerald-400 flex-shrink-0 pt-0.5">{icon}</div>
                                <span className="text-slate-100 text-sm sm:text-base font-medium leading-snug">
                                    {cleanText}
                                </span>
                            </div>
                        );
                    })}
                </div>

                {/* CTA */}
                <div className="mt-auto">
                    {bottomContent ? (
                        bottomContent
                    ) : (
                        <button
                            onClick={onSelect}
                            disabled={isButtonDisabled}
                            className={[
                                'w-full py-4 px-6 rounded-2xl font-bold uppercase tracking-wide transition-all duration-200',
                                'text-base sm:text-lg',
                                isButtonDisabled
                                    ? 'bg-white/10 text-white/30 cursor-not-allowed border border-white/5'
                                    : 'bg-white hover:bg-slate-50 text-slate-900 shadow-lg hover:shadow-xl hover:scale-[1.01] active:scale-[0.98]',
                                isLoading ? 'opacity-70 cursor-wait' : '',
                            ].join(' ')}
                        >
                            {isLoading ? (
                                <div className="flex items-center justify-center gap-2">
                                    <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
                                    <span>Ждем...</span>
                                </div>
                            ) : (
                                ctaText
                            )}
                        </button>
                    )}
                </div>

                {/* Decorative */}
                <div className="absolute top-0 right-0 w-64 h-64 bg-gradient-to-br from-emerald-500/10 to-transparent rounded-full blur-3xl -z-10" />
                <div className="absolute bottom-0 left-0 w-48 h-48 bg-gradient-to-tr from-cyan-500/10 to-transparent rounded-full blur-3xl -z-10" />
            </div>
        </div>
    );
}
