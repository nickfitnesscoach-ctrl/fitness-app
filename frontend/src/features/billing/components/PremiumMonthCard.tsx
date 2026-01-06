// billing/components/PremiumMonthCard.tsx
import { UtensilsCrossed, Zap, TrendingUp, Target } from 'lucide-react';
import { cleanFeatureText } from '../utils/text';

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

type IconType = 'utensils' | 'zap' | 'trending' | 'target';

const getIconForFeature = (text: string): IconType => {
    const lower = text.toLowerCase();
    if (lower.includes('свобода') || lower.includes('питания')) return 'utensils';
    if (lower.includes('мгновенный') || lower.includes('подсчет')) return 'zap';
    if (lower.includes('анализ') || lower.includes('прогресса')) return 'trending';
    if (lower.includes('адаптивный') || lower.includes('цель')) return 'target';
    return 'zap';
};

const getIcon = (iconType: IconType) => {
    switch (iconType) {
        case 'utensils':
            return <UtensilsCrossed className="w-4 h-4 text-emerald-400" />;
        case 'zap':
            return <Zap className="w-4 h-4 text-emerald-400" />;
        case 'trending':
            return <TrendingUp className="w-4 h-4 text-emerald-400" />;
        case 'target':
            return <Target className="w-4 h-4 text-emerald-400" />;
    }
};

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
        <div className="relative w-full max-w-md mx-auto">
            <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-3xl p-5 sm:p-6 shadow-xl border border-slate-700/50">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4 mb-6">
                    <div>
                        <p className="text-xs sm:text-sm text-slate-400 uppercase tracking-wide mb-1 sm:mb-2">
                            ПРЕМИУМ ФУНКЦИИ
                        </p>
                        <h2 className="text-2xl sm:text-3xl font-bold text-white">
                            {displayName}
                        </h2>
                        <p className="text-xs sm:text-sm text-emerald-400 font-medium mt-1 uppercase">
                            ПОЛНЫЙ БЕЗЛИМИТ
                        </p>
                    </div>
                    <div className="flex items-center gap-2 sm:flex-col sm:items-end sm:gap-1">
                        <span className="text-3xl sm:text-4xl font-bold text-white">
                            {price}₽
                        </span>
                        <span className="text-sm text-slate-400 uppercase">/МЕС</span>
                    </div>
                </div>

                <div className="bg-slate-800/50 backdrop-blur-sm rounded-2xl p-5 mb-6 space-y-4 border border-slate-700/30">
                    {features.map((feature, index) => {
                        const cleanText = cleanFeatureText(feature);
                        const iconType = getIconForFeature(cleanText);
                        return (
                            <div key={index} className="flex items-center gap-3">
                                <div className="w-8 h-8 rounded-lg bg-emerald-500/20 flex items-center justify-center flex-shrink-0">
                                    {getIcon(iconType)}
                                </div>
                                <span className="text-sm sm:text-base text-slate-200">
                                    {cleanText}
                                </span>
                            </div>
                        );
                    })}
                </div>

                {bottomContent ? (
                    bottomContent
                ) : (
                    <button
                        onClick={onSelect}
                        disabled={isButtonDisabled}
                        className={[
                            'w-full py-3.5 sm:py-4 bg-white text-slate-900 rounded-2xl font-bold text-sm sm:text-base transition-colors mt-auto uppercase',
                            isButtonDisabled
                                ? 'opacity-50 cursor-not-allowed bg-slate-700 text-slate-500 hover:bg-slate-700'
                                : 'hover:bg-slate-100',
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
        </div>
    );
}
