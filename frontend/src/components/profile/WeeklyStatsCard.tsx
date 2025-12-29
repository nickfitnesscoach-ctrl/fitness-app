import React from 'react';
import { TrendingUp, ChevronRight } from 'lucide-react';

interface WeeklyStatsCardProps {
    onClick: () => void;
    avgCalories: number;
    avgProtein: number;
    avgFat: number;
    avgCarbs: number;
}

const WeeklyStatsCard: React.FC<WeeklyStatsCardProps> = ({
    onClick,
    avgCalories,
    avgProtein,
    avgFat,
    avgCarbs
}) => {
    return (
        <div
            className="bg-white rounded-[var(--radius-card)] shadow-sm border border-gray-100 overflow-hidden cursor-pointer active:scale-[0.98] transition-all"
            onClick={onClick}
        >
            <div className="p-[var(--card-p)] flex items-center justify-between">
                <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-xl flex items-center justify-center shrink-0">
                        <TrendingUp size={20} className="text-white" />
                    </div>
                    <div className="min-w-0">
                        <h2 className="text-sm font-bold text-gray-900 leading-tight">Недельная статистика</h2>
                        <p className="text-[10px] text-gray-500 uppercase tracking-tighter">Среднее за 7 дней</p>
                    </div>
                </div>
                <ChevronRight size={20} className="text-gray-300 transition-transform" />
            </div>

            {/* Compact Metrics Strip */}
            <div className="px-[var(--card-p)] pb-[var(--card-p)] grid grid-cols-4 gap-2 border-t border-gray-50 pt-3">
                <Metric label="Ккал" value={avgCalories} color="text-orange-600" bgColor="bg-orange-50" />
                <Metric label="Белки" value={`${avgProtein}г`} color="text-blue-600" bgColor="bg-blue-50" />
                <Metric label="Жиры" value={`${avgFat}г`} color="text-yellow-600" bgColor="bg-yellow-50" />
                <Metric label="Углев." value={`${avgCarbs}г`} color="text-green-600" bgColor="bg-green-50" />
            </div>
        </div>
    );
};

const Metric: React.FC<{ label: string, value: string | number, color: string, bgColor: string }> = ({ label, value, color, bgColor }) => (
    <div className={`flex flex-col items-center justify-center py-1.5 px-1 rounded-lg ${bgColor}`}>
        <span className={`text-[11px] font-bold ${color} tabular-nums`}>{value}</span>
        <span className="text-[8px] text-gray-400 font-medium uppercase">{label}</span>
    </div>
);

export default WeeklyStatsCard;
