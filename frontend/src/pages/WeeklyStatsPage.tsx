import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    BarElement,
    Title,
    Tooltip,
    Legend,
    Filler
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';
import { Calendar, TrendingUp, Target, BarChart3 } from 'lucide-react';
import { useWeeklyKbjuStats } from '../hooks/useWeeklyKbjuStats';
import { PageContainer } from '../components/shared/PageContainer';
import PageHeader from '../components/PageHeader';

// Register ChartJS modules
ChartJS.register(
    CategoryScale,
    LinearScale,
    PointElement,
    LineElement,
    BarElement,
    Title,
    Tooltip,
    Legend,
    Filler
);

const WeeklyStatsPage: React.FC = () => {
    const navigate = useNavigate();
    const { dailyData, weeklyTotals, avgCalories, avgProtein, avgFat, avgCarbs, daysLogged, dateRange, loading } = useWeeklyKbjuStats();

    if (loading) {
        return (
            <div className="min-h-screen bg-gray-50">
                <PageHeader title="Статистика" fallbackRoute="/profile" />
                <div className="flex flex-col items-center justify-center h-[80vh]">
                    <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full"></div>
                </div>
            </div>
        );
    }

    const labels = dailyData.map(d => d.dayName);

    // Calories Chart Data
    const caloriesData = {
        labels,
        datasets: [
            {
                label: 'Калории',
                data: dailyData.map(d => d.calories),
                borderColor: 'rgb(249, 115, 22)',
                backgroundColor: 'rgba(249, 115, 22, 0.1)',
                tension: 0.4,
                fill: true,
                pointBackgroundColor: 'rgb(249, 115, 22)',
            },
        ],
    };

    // Macros Chart Data
    const macrosData = {
        labels,
        datasets: [
            {
                label: 'Белки',
                data: dailyData.map(d => d.protein),
                backgroundColor: 'rgb(59, 130, 246)',
            },
            {
                label: 'Жиры',
                data: dailyData.map(d => d.fat),
                backgroundColor: 'rgb(234, 179, 8)',
            },
            {
                label: 'Углеводы',
                data: dailyData.map(d => d.carbs),
                backgroundColor: 'rgb(34, 197, 94)',
            },
        ],
    };

    const chartOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false,
            },
            tooltip: {
                backgroundColor: 'rgba(0, 0, 0, 0.8)',
                padding: 10,
                titleFont: { size: 12, weight: 'bold' as const },
                bodyFont: { size: 12 },
                cornerRadius: 8,
            }
        },
        scales: {
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(0, 0, 0, 0.05)',
                },
                ticks: {
                    font: { size: 10 },
                    maxRotation: 0,
                }
            },
            x: {
                grid: {
                    display: false,
                },
                ticks: {
                    font: { size: 10, weight: 'bold' as const },
                }
            }
        },
    };

    const stackedOptions = {
        ...chartOptions,
        scales: {
            ...chartOptions.scales,
            y: {
                ...chartOptions.scales.y,
                stacked: true,
            },
            x: {
                ...chartOptions.scales.x,
                stacked: true,
            }
        }
    };

    if (daysLogged === 0) {
        return (
            <div className="min-h-screen bg-gray-50">
                <PageHeader title="Статистика" fallbackRoute="/profile" />
                <PageContainer className="py-12 flex flex-col items-center justify-center text-center">
                    <div className="w-20 h-20 bg-gray-100 rounded-full flex items-center justify-center mb-6">
                        <BarChart3 size={40} className="text-gray-300" />
                    </div>
                    <h2 className="text-xl font-bold text-gray-900 mb-2">Нет данных за неделю</h2>
                    <p className="text-gray-500 max-w-xs mb-8">
                        Начните добавлять приемы пищи, чтобы увидеть детальную статистику за текущую неделю.
                    </p>
                    <button
                        onClick={() => navigate('/')}
                        className="bg-blue-600 text-white px-6 py-3 rounded-xl font-bold active:scale-95 transition-all"
                    >
                        В дневник
                    </button>
                </PageContainer>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50">
            <PageHeader title="Недельная статистика" fallbackRoute="/profile" />

            <PageContainer className="py-6 space-y-[var(--section-gap)]">
                {/* Week Selector / Range Display */}
                <div className="text-center">
                    <div className="inline-flex items-center gap-2 bg-white px-4 py-2 rounded-full shadow-sm border border-gray-100">
                        <Calendar size={16} className="text-blue-500" />
                        <span className="text-sm font-bold text-gray-700">{dateRange}</span>
                    </div>
                    <p className="text-[10px] text-gray-400 uppercase tracking-widest mt-2 font-medium">
                        Дней с записями: <span className="text-blue-600">{daysLogged}</span> / 7
                    </p>
                </div>

                {/* Charts Section */}
                <div className="space-y-4">
                    <ChartCard title="Калории по дням" icon={<TrendingUp size={18} className="text-orange-500" />}>
                        <div className="h-64">
                            <Line data={caloriesData} options={chartOptions} />
                        </div>
                    </ChartCard>

                    <ChartCard title="КБЖУ по дням" icon={<BarChart3 size={18} className="text-blue-500" />}>
                        <div className="h-64">
                            <Bar data={macrosData} options={stackedOptions} />
                        </div>
                        <div className="flex justify-center gap-6 mt-4">
                            <LegendItem color="bg-blue-500" label="Белки" />
                            <LegendItem color="bg-yellow-400" label="Жиры" />
                            <LegendItem color="bg-green-500" label="Угл." />
                        </div>
                    </ChartCard>
                </div>

                {/* Weekly Totals / Averages */}
                <div className="grid grid-cols-1 gap-4">
                    <StatsGroup
                        title="Среднее за день"
                        icon={<Target size={18} className="text-purple-500" />}
                        metrics={[
                            { label: 'Ккал', value: avgCalories, color: 'text-orange-600' },
                            { label: 'Белки', value: `${avgProtein}г`, color: 'text-blue-600' },
                            { label: 'Жиры', value: `${avgFat}г`, color: 'text-yellow-600' },
                            { label: 'Углев.', value: `${avgCarbs}г`, color: 'text-green-600' },
                        ]}
                    />

                    <StatsGroup
                        title="Итого за неделю"
                        icon={<BarChart3 size={18} className="text-indigo-500" />}
                        metrics={[
                            { label: 'Ккал всего', value: weeklyTotals.calories, color: 'text-orange-600' },
                            { label: 'Белки всего', value: `${weeklyTotals.protein}г`, color: 'text-blue-600' },
                            { label: 'Жиры всего', value: `${weeklyTotals.fat}г`, color: 'text-yellow-600' },
                            { label: 'Углев. всего', value: `${weeklyTotals.carbs}г`, color: 'text-green-600' },
                        ]}
                    />
                </div>
            </PageContainer>
        </div>
    );
};

const ChartCard: React.FC<{ title: string, icon: React.ReactNode, children: React.ReactNode }> = ({ title, icon, children }) => (
    <div className="bg-white rounded-[var(--radius-card)] p-5 shadow-sm border border-gray-100">
        <div className="flex items-center gap-2 mb-6">
            {icon}
            <h3 className="font-bold text-gray-800">{title}</h3>
        </div>
        {children}
    </div>
);

const LegendItem: React.FC<{ color: string, label: string }> = ({ color, label }) => (
    <div className="flex items-center gap-1.5">
        <div className={`w-3 h-3 rounded-full ${color}`} />
        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wider">{label}</span>
    </div>
);

const StatsGroup: React.FC<{ title: string, icon: React.ReactNode, metrics: any[] }> = ({ title, icon, metrics }) => (
    <div className="bg-white rounded-[var(--radius-card)] p-5 shadow-sm border border-gray-100">
        <div className="flex items-center gap-2 mb-4">
            {icon}
            <h3 className="font-bold text-gray-800">{title}</h3>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {metrics.map((m, i) => (
                <div key={i} className="bg-gray-50 rounded-xl p-3 flex flex-col items-center">
                    <span className={`text-lg font-bold ${m.color} tabular-nums`}>{m.value}</span>
                    <span className="text-[10px] text-gray-400 font-bold uppercase tracking-widest">{m.label}</span>
                </div>
            ))}
        </div>
    </div>
);

export default WeeklyStatsPage;
