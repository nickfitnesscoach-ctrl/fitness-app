import React, { useState } from 'react';
import { ChevronRight, CreditCard, Bell, Globe, Clock } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const SettingsPage: React.FC = () => {
    const navigate = useNavigate();

    // Mock settings state
    const [notificationsEnabled, setNotificationsEnabled] = useState(true);

    return (
        <div className="p-4 pb-24 space-y-6 bg-gray-50 min-h-screen">
            <h1 className="text-2xl font-bold px-2">Настройки</h1>



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
    );
};

export default SettingsPage;
