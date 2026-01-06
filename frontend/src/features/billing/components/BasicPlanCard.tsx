// billing/components/BasicPlanCard.tsx
import { Zap, Calculator, Calendar } from 'lucide-react';
import { cleanFeatureText } from '../utils/text';

interface BasicPlanCardProps {
    displayName: string;
    price: number;
    features: string[];
    ctaText: string;
    isCurrent: boolean;
    isLoading: boolean;
    disabled?: boolean;
    onSelect: () => void;
}

type IconType = 'zap' | 'calculator' | 'calendar';

const getIconForFeature = (text: string): IconType => {
    const lower = text.toLowerCase();
    if (lower.includes('ai') || lower.includes('распозн') || lower.includes('фото')) return 'zap';
    if (lower.includes('кбжу') || lower.includes('расчет') || lower.includes('калор')) return 'calculator';
    if (lower.includes('истор') || lower.includes('дней') || lower.includes('дня')) return 'calendar';
    return 'zap';
};

const getIcon = (iconType: IconType) => {
    switch (iconType) {
        case 'zap':
            return <Zap className="w-5 h-5 text-gray-600 flex-shrink-0" />;
        case 'calculator':
            return <Calculator className="w-5 h-5 text-gray-600 flex-shrink-0" />;
        case 'calendar':
            return <Calendar className="w-5 h-5 text-gray-600 flex-shrink-0" />;
    }
};

export function BasicPlanCard({
    displayName,
    price,
    features,
    ctaText,
    isCurrent,
    isLoading,
    disabled,
    onSelect,
}: BasicPlanCardProps) {
    const isButtonDisabled = Boolean(disabled || isCurrent || isLoading);

    return (
        <div className="relative w-full max-w-md mx-auto">
            <div className="bg-white rounded-3xl p-5 sm:p-6 shadow-sm">
                <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3 sm:gap-4 mb-6">
                    <div>
                        <p className="text-xs sm:text-sm text-gray-500 uppercase tracking-wide mb-1 sm:mb-2">
                            ЛИМИТИРОВАННЫЙ ДОСТУП
                        </p>
                        <h2 className="text-2xl sm:text-3xl font-bold text-gray-900">
                            {displayName}
                        </h2>
                    </div>
                    <div className="flex items-center gap-2 sm:flex-col sm:items-end sm:gap-1">
                        <span className="text-3xl sm:text-4xl font-bold text-gray-900">
                            {price}₽
                        </span>
                    </div>
                </div>

                <div className="bg-gray-50 rounded-2xl p-5 mb-6 space-y-4">
                    {features.map((feature, index) => {
                        const cleanText = cleanFeatureText(feature);
                        const iconType = getIconForFeature(cleanText);
                        return (
                            <div key={index} className="flex items-center gap-3">
                                {getIcon(iconType)}
                                <span className="text-sm sm:text-base text-gray-700">{cleanText}</span>
                            </div>
                        );
                    })}
                </div>

                <button
                    onClick={onSelect}
                    disabled={isButtonDisabled}
                    className={[
                        'w-full py-3.5 sm:py-4 bg-transparent border-2 border-gray-900 text-gray-900 rounded-2xl font-bold text-sm sm:text-base transition-colors mt-auto uppercase',
                        isButtonDisabled
                            ? 'opacity-50 cursor-not-allowed bg-gray-100 border-gray-200 text-gray-400'
                            : 'hover:bg-gray-900 hover:text-white',
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
            </div>
        </div>
    );
}
