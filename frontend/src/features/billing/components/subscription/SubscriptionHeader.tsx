import React from 'react';

interface SubscriptionHeaderProps {
    topStatusText: string;
    headerTitle: string;
    headerSubtitle: string;
}

export const SubscriptionHeader: React.FC<SubscriptionHeaderProps> = ({
    topStatusText,
    headerTitle,
    headerSubtitle
}) => {
    return (
        <div className="flex flex-col items-center text-center space-y-2 mb-4">
            <div className="inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase bg-slate-100 text-slate-600 border border-slate-200">
                {topStatusText}
            </div>

            <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">
                {headerTitle}
            </h1>

            <p className="text-sm text-slate-500 max-w-[280px] leading-snug">
                {headerSubtitle}
            </p>
        </div>
    );
};
