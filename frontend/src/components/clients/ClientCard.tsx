import React from 'react';
import { Eye, MessageCircle, User } from 'lucide-react';
import { Application } from '../../types/application';

interface ClientCardProps {
    client: Application;
    onView: () => void;
    onOpenChat: () => void;
}

export const ClientCard: React.FC<ClientCardProps> = ({ client, onView, onOpenChat }) => {
    return (
        <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
            <div className="flex items-start gap-3 mb-3">
                <div className="w-12 h-12 bg-gray-100 rounded-full flex items-center justify-center text-gray-400">
                    <User size={24} />
                </div>
                <div className="flex-1">
                    <h3 className="font-bold text-gray-900">{client.first_name}</h3>
                    <p className="text-sm text-gray-500">@{client.username}</p>
                </div>
            </div>

            <div className="grid grid-cols-4 gap-2 mb-3 bg-gray-50 p-3 rounded-lg">
                <div className="text-center">
                    <div className="text-xs text-gray-500">Возраст</div>
                    <div className="font-bold text-gray-900">{client.details.age}</div>
                </div>
                <div className="text-center">
                    <div className="text-xs text-gray-500">Вес</div>
                    <div className="font-bold text-gray-900">{client.details.weight} кг</div>
                </div>
                <div className="text-center">
                    <div className="text-xs text-gray-500">Пол</div>
                    <div className="font-bold text-gray-900">{client.details.gender === 'Мужской' ? 'М' : 'Ж'}</div>
                </div>
                <div className="text-center">
                    <div className="text-xs text-gray-500">Акт.</div>
                    <div className="font-bold text-gray-900 text-xs">{client.details.activity_level.substring(0, 3)}</div>
                </div>
            </div>

            <div className="flex gap-2">
                <button
                    onClick={onView}
                    className="flex-1 bg-blue-500 text-white py-2.5 rounded-xl font-medium text-sm flex items-center justify-center gap-2 active:scale-95 transition-transform"
                >
                    <Eye size={18} />
                    Подробнее
                </button>
                <button
                    onClick={onOpenChat}
                    className="w-10 flex items-center justify-center bg-blue-50 text-blue-500 rounded-xl active:scale-95 transition-transform"
                >
                    <MessageCircle size={18} />
                </button>
            </div>
        </div>
    );
};
