import React from 'react';
import { ArrowLeft, MessageCircle, UserPlus, CheckCircle2, AlertCircle, ImageIcon } from 'lucide-react';
import { Application } from '../../types/application';
import { Avatar } from '../../../../components/Avatar';
import { InfoItem } from '../../../../components/common/InfoItem';
import { ACTIVITY_DESCRIPTIONS, TRAINING_LEVEL_DESCRIPTIONS } from '../../constants/applications';

interface ApplicationDetailsProps {
    application: Application;
    onBack: () => void;
    onMakeClient: () => void;
    onOpenChat: () => void;
    onChangeStatus: (status: 'new' | 'viewed' | 'contacted') => void;
    onDelete: () => void;
}

export const ApplicationDetails: React.FC<ApplicationDetailsProps> = ({
    application,
    onBack,
    onMakeClient,
    onOpenChat,
    onChangeStatus,
    onDelete
}) => {
    const activityInfo = (application.details.activity_level ? ACTIVITY_DESCRIPTIONS[application.details.activity_level] : null) || {
        title: application.details.activity_level ?? 'Не указана',
        description: '',
        icon: '❓'
    };

    const trainingInfo = (application.details.training_level ? TRAINING_LEVEL_DESCRIPTIONS[application.details.training_level] : null) || {
        title: application.details.training_level ?? 'Не указан',
        description: '',
        icon: '💪',
        color: 'text-gray-500'
    };

    return (
        <div className="space-y-4 pb-20">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <button onClick={onBack} className="p-2 -ml-2 text-gray-600">
                    <ArrowLeft size={24} />
                </button>
                <h1 className="text-xl font-bold">Результаты опроса</h1>
                <div className="w-8"></div> {/* Spacer for centering */}
            </div>

            {/* Profile Card */}
            <div className="bg-blue-500 text-white p-6 rounded-2xl shadow-lg flex items-center gap-4">
                <div className="w-16 h-16 bg-white/20 rounded-full overflow-hidden">
                    <Avatar
                        src={application.photo_url}
                        alt={application.first_name}
                        className="w-full h-full rounded-full object-cover"
                    />
                </div>
                <div>
                    <h2 className="text-2xl font-bold">{application.first_name}</h2>
                    <p className="opacity-90">@{application.username}</p>
                </div>
            </div>

            {/* Action Buttons */}
            <div className="grid grid-cols-2 gap-3">
                <button
                    onClick={onOpenChat}
                    className="flex items-center justify-center gap-2 bg-white border border-gray-200 py-3 rounded-xl font-medium text-gray-700 shadow-sm active:scale-95 transition-transform"
                >
                    <MessageCircle size={20} />
                    Написать в чат
                </button>
                <button
                    onClick={onMakeClient}
                    className="flex items-center justify-center gap-2 bg-blue-500 text-white py-3 rounded-xl font-medium shadow-sm active:scale-95 transition-transform"
                >
                    <UserPlus size={20} />
                    Сделать клиентом
                </button>
            </div>

            {/* Hint */}
            <div className="bg-gray-50 p-3 rounded-lg border border-gray-100 text-xs text-gray-500">
                Если не получается перейти в чат с клиентом, выполните поиск контакта по его username <span className="text-blue-600 font-medium">@{application.username}</span>
            </div>

            {/* Status Change Buttons */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
                <h3 className="font-bold text-sm mb-3 text-gray-700">Изменить статус заявки:</h3>
                <div className="flex gap-2">
                    <button
                        onClick={() => onChangeStatus('new')}
                        className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all ${application.status === 'new'
                                ? 'bg-blue-500 text-white'
                                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                    >
                        Новая
                    </button>
                    <button
                        onClick={() => onChangeStatus('viewed')}
                        className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all ${application.status === 'viewed'
                                ? 'bg-yellow-500 text-white'
                                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                    >
                        Просмотрено
                    </button>
                    <button
                        onClick={() => onChangeStatus('contacted')}
                        className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all ${application.status === 'contacted'
                                ? 'bg-green-500 text-white'
                                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                    >
                        Связался
                    </button>
                </div>
            </div>

            {/* Details Grid */}
            <div className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden">
                <div className="p-4 border-b border-gray-100">
                    <h3 className="font-bold text-lg">Основная информация</h3>
                </div>

                <div className="grid grid-cols-3 gap-3 p-4">
                    <div className="bg-white border-2 border-blue-300 p-3 rounded-xl">
                        <div className="text-xs text-gray-500 mb-1">Возраст:</div>
                        <div className="font-bold text-gray-900 text-right">{application.details.age} лет</div>
                    </div>
                    <InfoItem label="Пол:" value={application.details.gender ?? '—'} />
                    <InfoItem label="Рост:" value={`${application.details.height} см`} />
                    <InfoItem label="Вес:" value={`${application.details.weight} кг`} />
                    <InfoItem label="Целевой вес:" value={`${application.details.target_weight} кг`} />
                </div>

                <div className="p-4 border-t border-gray-100">
                    <div className="space-y-4">
                        {/* Activity Section */}
                        <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                            <div className="text-sm text-gray-500 mb-2">Активность</div>
                            <div className="flex items-start gap-3">
                                <div className="text-2xl">{activityInfo.icon}</div>
                                <div>
                                    <div className="font-bold text-gray-900">{activityInfo.title}</div>
                                    <div className="text-sm text-gray-600 mt-1 leading-relaxed">
                                        {activityInfo.description}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Training Level Section */}
                        <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                            <div className="text-sm text-gray-500 mb-2">Уровень тренированности</div>
                            <div className="flex items-start gap-3">
                                <div className="text-2xl">{trainingInfo.icon}</div>
                                <div>
                                    <div className="font-bold text-gray-900">{trainingInfo.title}</div>
                                    <div className="text-sm text-gray-600 mt-1 leading-relaxed">
                                        {trainingInfo.description}
                                    </div>
                                </div>
                            </div>
                        </div>

                        {/* Goals Section */}
                        <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                            <div className="text-sm text-gray-500 mb-3">Цели</div>
                            <div className="space-y-2">
                                {(application.details.goals ?? []).map((goal, index) => (
                                    <div key={index} className="flex items-center gap-2">
                                        <CheckCircle2 size={18} className="text-green-500 shrink-0" />
                                        <span className="text-gray-900 font-medium">{goal}</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Health Limitations Section */}
                        <div className="bg-red-50 p-4 rounded-xl border border-red-100">
                            <div className="text-sm text-red-500 mb-3 font-medium flex items-center gap-2">
                                <AlertCircle size={16} />
                                Ограничения по здоровью
                            </div>
                            <div className="space-y-2">
                                {(application.details.limitations ?? []).map((limitation, index) => (
                                    <div key={index} className="flex items-center gap-2">
                                        <CheckCircle2 size={18} className="text-red-500 shrink-0" />
                                        <span className="text-gray-900 font-medium">{limitation}</span>
                                    </div>
                                ))}
                                {(application.details.limitations ?? []).length === 0 && (
                                    <div className="text-gray-500 italic">Нет ограничений</div>
                                )}
                            </div>
                        </div>

                        {/* Body Type Section */}
                        <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                            <div className="text-sm text-gray-500 mb-3">Тип фигуры</div>
                            <div className="flex flex-col gap-3">
                                <div className="aspect-[3/4] w-full max-w-[200px] bg-gray-200 rounded-lg overflow-hidden self-center">
                                    {application.details.body_type?.image_url ? (
                                        <img
                                            src={application.details.body_type?.image_url}
                                            alt={application.details.body_type?.description ?? 'Тип фигуры'}
                                            className="w-full h-full object-cover"
                                        />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-gray-400">
                                            <ImageIcon size={48} />
                                        </div>
                                    )}
                                </div>
                                <div className="text-center">
                                    <div className="font-bold text-gray-900">{application.details.body_type?.description ?? 'Текущая форма'}</div>
                                </div>
                            </div>
                        </div>

                        {/* Desired Body Type Section */}
                        <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                            <div className="text-sm text-gray-500 mb-3">Желаемая форма</div>
                            <div className="flex flex-col gap-3">
                                <div className="aspect-[3/4] w-full max-w-[200px] bg-gray-200 rounded-lg overflow-hidden self-center">
                                    {application.details.desired_body_type?.image_url ? (
                                        <img
                                            src={application.details.desired_body_type?.image_url}
                                            alt={application.details.desired_body_type?.description ?? 'Желаемая форма'}
                                            className="w-full h-full object-cover"
                                        />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-gray-400">
                                            <ImageIcon size={48} />
                                        </div>
                                    )}
                                </div>
                                <div className="text-center">
                                    <div className="font-bold text-gray-900">{application.details.desired_body_type?.description ?? 'Желаемая форма'}</div>
                                </div>
                            </div>
                        </div>

                        {/* Timezone Section */}
                        <div className="bg-white p-4 rounded-xl border border-gray-100">
                            <div className="text-sm text-gray-500 mb-2">Часовой пояс</div>
                            <div className="bg-gray-50 p-3 rounded-lg text-center">
                                <div className="font-bold text-gray-900 text-lg">{application.details.timezone}</div>
                            </div>
                        </div>

                        {/* Delete Button */}
                        <div className="pt-4 border-t border-gray-100">
                            <button
                                onClick={onDelete}
                                className="w-full py-3 px-4 bg-red-50 text-red-600 rounded-xl font-medium hover:bg-red-100 active:scale-95 transition-all flex items-center justify-center gap-2"
                            >
                                <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <polyline points="3 6 5 6 21 6"></polyline>
                                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                                    <line x1="10" y1="11" x2="10" y2="17"></line>
                                    <line x1="14" y1="11" x2="14" y2="17"></line>
                                </svg>
                                Удалить заявку
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
};
