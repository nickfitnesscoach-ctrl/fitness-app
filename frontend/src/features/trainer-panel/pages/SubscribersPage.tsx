import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft, Crown, Users, Star, Calendar, DollarSign, RefreshCw } from 'lucide-react';
import { api } from '../../../services/api';
import { formatBillingDate } from '../../billing';

interface Subscriber {
    id: number;
    telegram_id: number;
    first_name: string;
    last_name?: string;
    username?: string;
    plan_type: 'free' | 'monthly' | 'yearly';
    subscribed_at?: string;
    expires_at?: string;
    is_active: boolean;
}

interface Stats {
    total: number;
    free: number;
    monthly: number;
    yearly: number;
    revenue: number;
}

const PLAN_LABELS: Record<string, { label: string; color: string; bgColor: string }> = {
    'free': { label: 'Бесплатный', color: 'text-gray-600', bgColor: 'bg-gray-100' },
    'monthly': { label: 'Месячный', color: 'text-blue-600', bgColor: 'bg-blue-100' },
    'yearly': { label: 'Годовой', color: 'text-purple-600', bgColor: 'bg-purple-100' }
};

const SubscribersPage: React.FC = () => {
    const navigate = useNavigate();
    const [subscribers, setSubscribers] = useState<Subscriber[]>([]);
    const [stats, setStats] = useState<Stats>({ total: 0, free: 0, monthly: 0, yearly: 0, revenue: 0 });
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState<'all' | 'free' | 'monthly' | 'yearly'>('all');

    const loadSubscribers = async () => {
        setLoading(true);
        try {
            const data = await api.getSubscribers();
            setSubscribers(data.subscribers || []);
            setStats(data.stats || { total: 0, free: 0, monthly: 0, yearly: 0, revenue: 0 });
        } catch (error) {
            console.error('Error loading subscribers:', error);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadSubscribers();
    }, []);

    const filteredSubscribers = filter === 'all'
        ? subscribers
        : subscribers.filter(s => s.plan_type === filter);

    return (
        <div className="min-h-screen bg-gray-50">
            {/* Header */}
            <div className="bg-white border-b sticky top-0 z-10">
                <div className="flex items-center gap-3 p-4">
                    <button onClick={() => navigate('/panel')} className="p-2 hover:bg-gray-100 rounded-full">
                        <ArrowLeft size={20} />
                    </button>
                    <h1 className="text-xl font-bold">Подписчики</h1>
                    <button
                        onClick={loadSubscribers}
                        className="ml-auto p-2 hover:bg-gray-100 rounded-full"
                        disabled={loading}
                    >
                        <RefreshCw size={20} className={loading ? 'animate-spin' : ''} />
                    </button>
                </div>
            </div>

            <div className="p-4 space-y-4">
                {/* Stats Cards */}
                <div className="grid grid-cols-2 gap-3">
                    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
                        <div className="flex items-center gap-2 mb-1">
                            <Users size={18} className="text-blue-500" />
                            <span className="text-xs text-gray-500">Всего</span>
                        </div>
                        <p className="text-2xl font-bold">{stats.total}</p>
                    </div>

                    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
                        <div className="flex items-center gap-2 mb-1">
                            <DollarSign size={18} className="text-green-500" />
                            <span className="text-xs text-gray-500">Доход</span>
                        </div>
                        <p className="text-2xl font-bold">{stats.revenue.toLocaleString()}₽</p>
                    </div>

                    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
                        <div className="flex items-center gap-2 mb-1">
                            <Star size={18} className="text-yellow-500" />
                            <span className="text-xs text-gray-500">Месячных</span>
                        </div>
                        <p className="text-2xl font-bold text-blue-600">{stats.monthly}</p>
                    </div>

                    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
                        <div className="flex items-center gap-2 mb-1">
                            <Crown size={18} className="text-purple-500" />
                            <span className="text-xs text-gray-500">Годовых</span>
                        </div>
                        <p className="text-2xl font-bold text-purple-600">{stats.yearly}</p>
                    </div>
                </div>

                {/* Filter Tabs */}
                <div className="flex gap-2 overflow-x-auto pb-2">
                    {[
                        { key: 'all', label: 'Все', count: stats.total },
                        { key: 'free', label: 'Бесплатные', count: stats.free },
                        { key: 'monthly', label: 'Месячные', count: stats.monthly },
                        { key: 'yearly', label: 'Годовые', count: stats.yearly }
                    ].map(tab => (
                        <button
                            key={tab.key}
                            onClick={() => setFilter(tab.key as any)}
                            className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${
                                filter === tab.key
                                    ? 'bg-blue-600 text-white'
                                    : 'bg-white text-gray-600 border border-gray-200'
                            }`}
                        >
                            {tab.label} ({tab.count})
                        </button>
                    ))}
                </div>

                {/* Subscribers List */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                    {loading ? (
                        <div className="p-8 text-center">
                            <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-2"></div>
                            <p className="text-gray-500">Загрузка...</p>
                        </div>
                    ) : filteredSubscribers.length === 0 ? (
                        <div className="p-8 text-center text-gray-500">
                            <Users size={48} className="mx-auto mb-2 opacity-30" />
                            <p>Нет подписчиков</p>
                        </div>
                    ) : (
                        <div className="divide-y divide-gray-100">
                            {filteredSubscribers.map((subscriber) => {
                                const planInfo = PLAN_LABELS[subscriber.plan_type] || PLAN_LABELS.free;

                                return (
                                    <div key={subscriber.id} className="p-4 hover:bg-gray-50">
                                        <div className="flex items-start justify-between">
                                            <div className="flex-1">
                                                <div className="flex items-center gap-2 mb-1">
                                                    <span className="font-medium">
                                                        {subscriber.first_name} {subscriber.last_name || ''}
                                                    </span>
                                                    {subscriber.plan_type !== 'free' && (
                                                        <Crown size={14} className="text-yellow-500" />
                                                    )}
                                                </div>
                                                {subscriber.username && (
                                                    <p className="text-sm text-gray-500">@{subscriber.username}</p>
                                                )}
                                                {subscriber.expires_at && subscriber.plan_type !== 'free' && (
                                                    <div className="flex items-center gap-1 mt-1 text-xs text-gray-400">
                                                        <Calendar size={12} />
                                                        <span>до {formatBillingDate(subscriber.expires_at)}</span>
                                                    </div>
                                                )}
                                            </div>
                                            <span className={`px-3 py-1 rounded-full text-xs font-medium ${planInfo.bgColor} ${planInfo.color}`}>
                                                {planInfo.label}
                                            </span>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* Summary */}
                {!loading && stats.total > 0 && (
                    <div className="bg-gradient-to-r from-blue-500 to-purple-500 rounded-2xl p-4 text-white">
                        <p className="text-sm opacity-80 mb-1">Конверсия в платные</p>
                        <p className="text-2xl font-bold">
                            {stats.total > 0
                                ? Math.round(((stats.monthly + stats.yearly) / stats.total) * 100)
                                : 0}%
                        </p>
                        <p className="text-xs opacity-70 mt-1">
                            {stats.monthly + stats.yearly} из {stats.total} пользователей
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default SubscribersPage;
