import React, { useState } from 'react';
import { ChevronRight, CreditCard, Bell, Globe, Clock, Sun, Moon, Monitor } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import PageHeader from '../components/PageHeader';
// F-020: Theme support
import { useTheme } from '../contexts/ThemeContext';

const SettingsPage: React.FC = () => {
    const navigate = useNavigate();
    const { theme, setTheme, effectiveTheme } = useTheme();

    // Mock settings state
    const [notificationsEnabled, setNotificationsEnabled] = useState(true);

    return (
        <div className="min-h-screen bg-gray-50 pb-24">
            <PageHeader title="Настройки" fallbackRoute="/profile" />

            <div className="p-4 space-y-6">



                {/* App Settings Section */}
                <div className="space-y-2">
                    <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wider px-2">
                        Приложение
                    </h2>
                    <div className="bg-white rounded-2xl overflow-hidden shadow-sm">
                        {/* Subscription & Payment Link */}
                        <div
                            onClick={() => navigate('/settings/subscription')}
                            className="p-4 border-b border-gray-100 flex justify-between items-center active:bg-gray-50 cursor-pointer transition-colors"
                        >
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-indigo-50 text-indigo-500 rounded-lg">
                                    <CreditCard size={18} />
                                </div>
                                <span className="text-gray-900">Подписка и оплата</span>
                            </div>
                            <ChevronRight size={20} className="text-gray-300" />
                        </div>

                        {/* Notifications */}
                        <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-blue-50 text-blue-500 rounded-lg">
                                    <Bell size={18} />
                                </div>
                                <span className="text-gray-900">Уведомления</span>
                            </div>
                            <button
                                onClick={() => setNotificationsEnabled(!notificationsEnabled)}
                                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors focus:outline-none ${notificationsEnabled ? 'bg-blue-500' : 'bg-gray-200'
                                    }`}
                            >
                                <span
                                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${notificationsEnabled ? 'translate-x-6' : 'translate-x-1'
                                        }`}
                                />
                            </button>
                        </div>

                        {/* Language */}
                        <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-purple-50 text-purple-500 rounded-lg">
                                    <Globe size={18} />
                                </div>
                                <span className="text-gray-900">Язык</span>
                            </div>
                            <span className="text-gray-500 text-sm">Русский</span>
                        </div>

                        {/* F-020: Theme Selector */}
                        <div className="p-4 border-b border-gray-100">
                            <div className="flex items-center gap-3 mb-3">
                                <div className={`p-2 rounded-lg ${effectiveTheme === 'dark' ? 'bg-gray-700 text-yellow-400' : 'bg-yellow-50 text-yellow-500'}`}>
                                    {effectiveTheme === 'dark' ? <Moon size={18} /> : <Sun size={18} />}
                                </div>
                                <span className="text-gray-900 dark:text-gray-100">Тема оформления</span>
                            </div>
                            <div className="flex gap-2 ml-11">
                                <button
                                    onClick={() => setTheme('light')}
                                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                                        theme === 'light' 
                                            ? 'bg-blue-500 text-white' 
                                            : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                                    }`}
                                >
                                    <Sun size={14} />
                                    Светлая
                                </button>
                                <button
                                    onClick={() => setTheme('dark')}
                                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                                        theme === 'dark' 
                                            ? 'bg-blue-500 text-white' 
                                            : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                                    }`}
                                >
                                    <Moon size={14} />
                                    Тёмная
                                </button>
                                <button
                                    onClick={() => setTheme('system')}
                                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-colors ${
                                        theme === 'system' 
                                            ? 'bg-blue-500 text-white' 
                                            : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                                    }`}
                                >
                                    <Monitor size={14} />
                                    Авто
                                </button>
                            </div>
                        </div>

                        {/* Timezone */}
                        <div className="p-4 border-b border-gray-100 flex justify-between items-center">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-orange-50 text-orange-500 rounded-lg">
                                    <Clock size={18} />
                                </div>
                                <span className="text-gray-900">Часовой пояс</span>
                            </div>
                            <span className="text-gray-500 text-sm">GMT+3</span>
                        </div>

                        {/* Units (Optional) */}
                        <div className="p-4 flex justify-between items-center">
                            <div className="flex items-center gap-3">
                                <div className="p-2 bg-green-50 text-green-500 rounded-lg">
                                    <span className="text-xs font-bold">KG</span>
                                </div>
                                <span className="text-gray-900">Единицы измерения</span>
                            </div>
                            <span className="text-gray-500 text-sm">Вес: кг, Рост: см</span>
                        </div>
                    </div>
                </div>

                <div className="text-center text-xs text-gray-400 pt-4">
                    Version 1.0.0
                </div>
            </div>
        </div>
    );
};

export default SettingsPage;
