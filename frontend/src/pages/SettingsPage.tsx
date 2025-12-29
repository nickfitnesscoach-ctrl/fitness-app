import React, { useState } from 'react';
import { ChevronRight, CreditCard, Bell, Globe, Clock, Sun, Moon, Monitor } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../components/PageHeader';
import { useTheme } from '../contexts/ThemeContext';
import { PageContainer } from '../components/shared/PageContainer';

const SettingsPage: React.FC = () => {
    const navigate = useNavigate();
    const { theme, setTheme, effectiveTheme } = useTheme();
    const [notificationsEnabled, setNotificationsEnabled] = useState(true);

    return (
        <div className="min-h-screen bg-gray-50">
            <PageHeader title="Настройки" fallbackRoute="/profile" />

            <PageContainer className="py-6 space-y-[var(--section-gap)]">
                {/* App Settings Section */}
                <div className="space-y-3">
                    <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-widest px-2">
                        Приложение
                    </h2>
                    <div className="bg-white rounded-[var(--radius-card)] overflow-hidden shadow-sm border border-gray-100">
                        <div
                            onClick={() => navigate('/settings/subscription')}
                            className="p-4 border-b border-gray-100 flex justify-between items-center active:bg-gray-50 cursor-pointer transition-colors"
                        >
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-indigo-50 text-indigo-500 rounded-lg">
                                    <CreditCard size={18} />
                                </div>
                                <span className="text-gray-900 font-medium">Подписка и оплата</span>
                            </div>
                            <ChevronRight size={20} className="text-gray-300" />
                        </div>

                        <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-blue-50 text-blue-500 rounded-lg">
                                    <Bell size={18} />
                                </div>
                                <span className="text-gray-900 font-medium">Уведомления</span>
                            </div>
                            <button
                                onClick={() => setNotificationsEnabled(!notificationsEnabled)}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${notificationsEnabled ? 'bg-blue-500' : 'bg-gray-200'}`}
                            >
                                <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${notificationsEnabled ? 'translate-x-6' : 'translate-x-1'}`} />
                            </button>
                        </div>

                        <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-purple-50 text-purple-500 rounded-lg">
                                    <Globe size={18} />
                                </div>
                                <span className="text-gray-900 font-medium">Язык</span>
                            </div>
                            <span className="text-gray-500 text-sm">Русский</span>
                        </div>

                        <div className="p-4 border-b border-gray-100">
                            <div className="flex items-center gap-3 mb-4">
                                <div className={`p-2 rounded-lg ${effectiveTheme === 'dark' ? 'bg-gray-700 text-yellow-400' : 'bg-yellow-50 text-yellow-500'}`}>
                                    {effectiveTheme === 'dark' ? <Moon size={18} /> : <Sun size={18} />}
                                </div>
                                <span className="text-gray-900 font-medium">Тема оформления</span>
                            </div>
                            <div className="flex gap-2 ml-10">
                                <ThemeButton active={theme === 'light'} onClick={() => setTheme('light')} icon={<Sun size={14} />} label="Светлая" />
                                <ThemeButton active={theme === 'dark'} onClick={() => setTheme('dark')} icon={<Moon size={14} />} label="Тёмная" />
                                <ThemeButton active={theme === 'system'} onClick={() => setTheme('system')} icon={<Monitor size={14} />} label="Авто" />
                            </div>
                        </div>

                        <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-orange-50 text-orange-500 rounded-lg">
                                    <Clock size={18} />
                                </div>
                                <span className="text-gray-900 font-medium">Часовой пояс</span>
                            </div>
                            <span className="text-gray-500 text-sm tabular-nums">GMT+3</span>
                        </div>

                        <div className="p-4 flex justify-between items-center">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-green-50 text-green-500 rounded-lg">
                                    <span className="text-xs font-bold">KG</span>
                                </div>
                                <span className="text-gray-900 font-medium">Единицы измерения</span>
                            </div>
                            <span className="text-gray-500 text-sm">Вес: кг, Рост: см</span>
                        </div>
                    </div>
                </div>

                <div className="text-center text-[10px] text-gray-400 pt-4 uppercase tracking-widest font-medium tabular-nums">
                    Version 1.0.0
                </div>
            </PageContainer>
        </div>
    );
};

const ThemeButton: React.FC<{ active: boolean, onClick: () => void, icon: React.ReactNode, label: string }> = ({ active, onClick, icon, label }) => (
    <button
        onClick={onClick}
        className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold transition-all active:scale-95 ${active ? 'bg-blue-600 text-white shadow-md' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}
    >
        {icon}
        {label}
    </button>
);

export default SettingsPage;
