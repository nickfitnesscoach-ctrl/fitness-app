// billing/components/PlanPriceStack.tsx
import React from 'react';

interface PlanPriceStackProps {
    priceMain: string | number;
    priceUnit?: string;
    oldPrice?: string | number;
    priceSubtext?: string;
    alignRight?: boolean;
    isDark?: boolean;
}

function formatNumber(v: string | number): string {
    if (typeof v === 'number') return v.toLocaleString('ru-RU');
    return String(v);
}

/**
 * Stable 2-row layout:
 * Row1: main + unit
 * Row2: oldPrice + subtext (one line) with fixed min height to prevent jumps
 */
export const PlanPriceStack: React.FC<PlanPriceStackProps> = ({
    priceMain,
    priceUnit,
    oldPrice,
    priceSubtext,
    alignRight = false,
    isDark = false,
}) => {
    const mainTextColor = isDark ? 'text-white' : 'text-slate-900';
    const unitTextColor = isDark ? 'text-slate-300' : 'text-slate-600';
    const secondaryTextColor = isDark ? 'text-slate-400' : 'text-slate-500';

    const align = alignRight ? 'items-end text-right' : 'items-start text-left';

    return (
        <div className={`shrink-0 flex flex-col ${align} min-w-[7.5rem]`}>
            {/* Row 1 */}
            <div className={`flex items-baseline gap-1 ${alignRight ? 'justify-end' : 'justify-start'}`}>
                <span className={`tabular-nums font-extrabold leading-none ${mainTextColor} text-4xl sm:text-5xl`}>
                    {formatNumber(priceMain)}
                </span>
                {priceUnit ? (
                    <span className={`whitespace-nowrap font-bold leading-none ${unitTextColor} text-base sm:text-xl`}>
                        {priceUnit}
                    </span>
                ) : null}
            </div>

            {/* Row 2 */}
            <div
                className={`mt-2 flex items-baseline gap-3 min-h-[1.25rem] ${alignRight ? 'justify-end' : 'justify-start'}`}
            >
                {oldPrice != null ? (
                    <span className={`${secondaryTextColor} text-sm font-semibold line-through tabular-nums whitespace-nowrap`}>
                        {formatNumber(oldPrice)} ₽
                    </span>
                ) : null}

                <span className={`${secondaryTextColor} text-sm font-medium whitespace-nowrap`}>
                    {priceSubtext ?? (oldPrice != null ? '\u00A0' : '\u00A0')}
                </span>
            </div>
        </div>
    );
};
