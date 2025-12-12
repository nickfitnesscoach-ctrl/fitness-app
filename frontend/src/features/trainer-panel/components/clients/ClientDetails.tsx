import React from 'react';
import { ArrowLeft, MessageCircle, CheckCircle2, AlertCircle, ImageIcon, Trash2 } from 'lucide-react';
import { Application } from '../../types/application';
import { Avatar } from '../../../../components/Avatar';
import { InfoItem } from '../../../../components/common/InfoItem';
import { ACTIVITY_DESCRIPTIONS, TRAINING_LEVEL_DESCRIPTIONS } from '../../constants/applications';

interface ClientDetailsProps {
    client: Application;
    onBack: () => void;
    onOpenChat: (username: string) => void;
    onRemoveClient: (id: number) => void;
}

export const ClientDetails: React.FC<ClientDetailsProps> = ({
    client,
    onBack,
    onOpenChat,
    onRemoveClient
}) => {
    const activityInfo = ACTIVITY_DESCRIPTIONS[client.details.activity_level] || {
        title: client.details.activity_level,
        description: '',
        icon: '❓'
    };

    const trainingInfo = TRAINING_LEVEL_DESCRIPTIONS[client.details.training_level] || {
        title: client.details.training_level,
        description: '',
        icon: '💪',
        color: 'text-gray-500'
    };

    return (
        <div className="space-y-4 pb-20">
            <div className="flex items-center justify-between mb-4">
                <button onClick={onBack} className="p-2 -ml-2 text-gray-600">
                    <ArrowLeft size={24} />
                </button>
                <h1 className="text-xl font-bold">Профиль клиента</h1>
                <div className="w-8"></div>
            </div>

            <div className="bg-blue-500 text-white p-6 rounded-2xl shadow-lg flex items-center gap-4">
                <div className="w-16 h-16 bg-white/20 rounded-full overflow-hidden">
                    <Avatar
                        src={client.photo_url}
                        alt={client.first_name}
                        className="w-full h-full rounded-full object-cover"
                    />
                </div>
                <div>
                    <h2 className="text-2xl font-bold">{client.first_name}</h2>
                    <p className="opacity-90">@{client.username}</p>
                </div>
            </div>

            <button
                onClick={() => onOpenChat(client.username)}
                className="w-full flex items-center justify-center gap-2 bg-white border border-gray-200 py-3 rounded-xl font-medium text-gray-700 shadow-sm active:scale-95 transition-transform"
            >
                <MessageCircle size={20} />
                Написать в чат
            </button>

            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <div className="p-4 border-b border-gray-100">
                    <h3 className="font-bold text-lg">Основная информация</h3>
                </div>

                <div className="grid grid-cols-3 gap-3 p-4">
                    <div className="bg-white border-2 border-blue-300 p-3 rounded-xl">
                        <div className="text-xs text-gray-500 mb-1">Возраст:</div>
                        <div className="font-bold text-gray-900 text-right">{client.details.age} лет</div>
                    </div>
                    <InfoItem label="Пол:" value={client.details.gender} />
                    <InfoItem label="Рост:" value={`${client.details.height} см`} />
                    <InfoItem label="Вес:" value={`${client.details.weight} кг`} />
                    <InfoItem label="Целевой вес:" value={`${client.details.target_weight} кг`} />
                </div>

                <div className="p-4 border-t border-gray-100">
                    <div className="space-y-4">
                        <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                            <div className="text-sm text-gray-500 mb-2">Активность</div>
                            <div className="flex items-start gap-3">
                                <div className="text-2xl">{activityInfo.icon}</div>
                                <div>
                                    <div className="font-bold text-gray-900">{activityInfo.title}</div>
                                    <div className="text-sm text-gray-600 mt-1 leading-relaxed">{activityInfo.description}</div>
                                </div>
                            </div>
                        </div>

                        <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                            <div className="text-sm text-gray-500 mb-2">Уровень тренированности</div>
                            <div className="flex items-start gap-3">
                                <div className="text-2xl">{trainingInfo.icon}</div>
                                <div>
                                    <div className="font-bold text-gray-900">{trainingInfo.title}</div>
                                    <div className="text-sm text-gray-600 mt-1 leading-relaxed">{trainingInfo.description}</div>
                                </div>
                            </div>
                        </div>

                        <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                            <div className="text-sm text-gray-500 mb-3">Цели</div>
                            <div className="space-y-2">
                                {client.details.goals.map((goal, index) => (
                                    <div key={index} className="flex items-center gap-2">
                                        <CheckCircle2 size={18} className="text-green-500 shrink-0" />
                                        <span className="text-gray-900 font-medium">{goal}</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        <div className="bg-red-50 p-4 rounded-xl border border-red-100">
                            <div className="text-sm text-red-500 mb-3 font-medium flex items-center gap-2">
                                <AlertCircle size={16} />
                                Ограничения по здоровью
                            </div>
                            <div className="space-y-2">
                                {client.details.limitations.map((limitation, index) => (
                                    <div key={index} className="flex items-center gap-2">
                                        <CheckCircle2 size={18} className="text-red-500 shrink-0" />
                                        <span className="text-gray-900 font-medium">{limitation}</span>
                                    </div>
                                ))}
                                {client.details.limitations.length === 0 && (
                                    <div className="text-gray-500 italic">Нет ограничений</div>
                                )}
                            </div>
                        </div>

                        <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                            <div className="text-sm text-gray-500 mb-3">Тип фигуры</div>
                            <div className="flex flex-col gap-3">
                                <div className="aspect-[3/4] w-full max-w-[200px] bg-gray-200 rounded-lg overflow-hidden self-center">
                                    {client.details.body_type.image_url ? (
                                        <img
                                            src={client.details.body_type.image_url}
                                            alt={client.details.body_type.description}
                                            className="w-full h-full object-cover"
                                        />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-gray-400">
                                            <ImageIcon size={48} />
                                        </div>
                                    )}
                                </div>
                                <div className="text-center">
                                    <div className="font-bold text-gray-900">{client.details.body_type.description}</div>
                                </div>
                            </div>
                        </div>

                        <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                            <div className="text-sm text-gray-500 mb-3">Желаемая форма</div>
                            <div className="flex flex-col gap-3">
                                <div className="aspect-[3/4] w-full max-w-[200px] bg-gray-200 rounded-lg overflow-hidden self-center">
                                    {client.details.desired_body_type.image_url ? (
                                        <img
                                            src={client.details.desired_body_type.image_url}
                                            alt={client.details.desired_body_type.description}
                                            className="w-full h-full object-cover"
                                        />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-gray-400">
                                            <ImageIcon size={48} />
                                        </div>
                                    )}
                                </div>
                                <div className="text-center">
                                    <div className="font-bold text-gray-900">{client.details.desired_body_type.description}</div>
                                </div>
                            </div>
                        </div>

                        <div className="bg-white p-4 rounded-xl border border-gray-100">
                            <div className="text-sm text-gray-500 mb-2">Часовой пояс</div>
                            <div className="bg-gray-50 p-3 rounded-lg text-center">
                                <div className="font-bold text-gray-900 text-lg">{client.details.timezone}</div>
                            </div>
                        </div>

                        <div className="pt-4 border-t border-gray-100">
                            <button
                                onClick={() => onRemoveClient(client.id)}
                                className="w-full py-3 px-4 bg-red-50 text-red-600 rounded-xl font-medium hover:bg-red-100 active:scale-95 transition-all flex items-center justify-center gap-2"
                            >
                                <Trash2 size={20} />
                                Удалить из клиентов
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
