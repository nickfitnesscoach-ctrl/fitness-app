import React from 'react';
import { useNavigate } from 'react-router-dom';
import { Users, ClipboardList, Utensils, Crown } from 'lucide-react';

export const Dashboard: React.FC = () => {
    const navigate = useNavigate();

    return (
        <div className="dashboard trainer-panel flex flex-col items-center justify-center min-h-[80vh] p-5">
            <header className="panel-header text-center mb-12">
                <h1 className="text-5xl font-extrabold mb-2">Панель тренера</h1>
            </header>

            <div className="panel-grid flex flex-wrap justify-center items-center gap-6">
                <button
                    className="panel-card flex flex-col items-center justify-center p-5 bg-white border border-gray-200 rounded-2xl shadow-sm hover:scale-105 transition-transform w-52 h-52"
                    onClick={() => navigate('/panel/clients')}
                >
                    <div className="icon-wrapper blue w-16 h-16 rounded-full flex items-center justify-center text-white bg-blue-600 mb-4">
                        <Users size={32} />
                    </div>
                    <span className="text-lg font-semibold text-gray-900">Клиенты</span>
                </button>

                <button
                    className="panel-card flex flex-col items-center justify-center p-5 bg-white border border-gray-200 rounded-2xl shadow-sm hover:scale-105 transition-transform w-52 h-52"
                    onClick={() => navigate('/panel/applications')}
                >
                    <div className="icon-wrapper blue w-16 h-16 rounded-full flex items-center justify-center text-white bg-blue-600 mb-4">
                        <ClipboardList size={32} />
                    </div>
                    <span className="text-lg font-semibold text-gray-900">Заявки</span>
                </button>

                <button
                    className="panel-card flex flex-col items-center justify-center p-5 bg-white border border-gray-200 rounded-2xl shadow-sm hover:scale-105 transition-transform w-52 h-52"
                    onClick={() => navigate('/panel/subscribers')}
                >
                    <div className="icon-wrapper w-16 h-16 rounded-full flex items-center justify-center text-white bg-gradient-to-br from-yellow-500 to-orange-500 mb-4">
                        <Crown size={32} />
                    </div>
                    <span className="text-lg font-semibold text-gray-900">Подписки</span>
                </button>

                <button
                    className="panel-card flex flex-col items-center justify-center p-5 bg-white border border-gray-200 rounded-2xl shadow-sm hover:scale-105 transition-transform w-52 h-52"
                    onClick={() => navigate('/')}
                >
                    <div className="icon-wrapper w-16 h-16 rounded-full flex items-center justify-center text-white bg-gradient-to-br from-orange-500 to-red-500 mb-4">
                        <Utensils size={32} />
                    </div>
                    <span className="text-lg font-semibold text-gray-900">КБЖУ Трекер</span>
                </button>
            </div>
        </div>
    );
};
