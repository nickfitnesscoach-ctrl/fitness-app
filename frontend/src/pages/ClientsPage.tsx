import React, { useState } from 'react';
import { Search, UserPlus, Eye, MessageCircle, ArrowLeft, User, CheckCircle2, AlertCircle, ImageIcon, Trash2 } from 'lucide-react';
import { useClients } from '../contexts/ClientsContext';
import { Application } from '../services/mockData';
import { useNavigate } from 'react-router-dom';
import { Avatar } from '../components/Avatar';

const ACTIVITY_DESCRIPTIONS: Record<string, { title: string; description: string; icon: string }> = {
    'Минимальная': {
        title: 'Минимальная',
        description: 'Преимущественно сидячий образ жизни. Работа за компьютером, мало перемещений. Менее 3 000 шагов в день.',
        icon: '🧘'
    },
    'Низкая': {
        title: 'Низкая',
        description: 'Больше бытовых дел и перемещений. Иногда пешие дистанции, небольшие прогулки. 3 000–7 000 шагов в день.',
        icon: '🚶'
    },
    'Средняя': {
        title: 'Средняя',
        description: 'Много ходьбы в течение дня. Работа на ногах, активные бытовые нагрузки. 7 000–12 000 шагов в день.',
        icon: '🏃'
    },
    'Высокая': {
        title: 'Высокая',
        description: 'Постоянное движение. Физически активная работа, много перемещений, быстрая ходьба. Более 12 000 шагов в день.',
        icon: '🔥'
    }
};

const TRAINING_LEVEL_DESCRIPTIONS: Record<string, { title: string; description: string; icon: string; color: string }> = {
    'Новичок': {
        title: 'Новичок',
        description: 'не тренируюсь / реже 1 раза в неделю',
        icon: '🟢',
        color: 'text-green-500'
    },
    'Средний': {
        title: 'Средний',
        description: '2–3 тренировки в неделю, базовое понимание упражнений',
        icon: '🟡',
        color: 'text-yellow-500'
    },
    'Продвинутый': {
        title: 'Продвинутый',
        description: '4+ тренировки в неделю, уверенно выполняю сложные упражнения',
        icon: '🔴',
        color: 'text-red-500'
    },
    'Домашний формат': {
        title: 'Домашний формат',
        description: 'тренируюсь дома время от времени',
        icon: '🏠',
        color: 'text-orange-500'
    }
};

const ClientsPage = () => {
    const { clients, removeClient } = useClients();
    const navigate = useNavigate();
    const [selectedClient, setSelectedClient] = useState<Application | null>(null);
    const [searchTerm, setSearchTerm] = useState('');

    const filteredClients = clients.filter(client =>
        client.first_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        client.username.toLowerCase().includes(searchTerm.toLowerCase())
    );

    const handleRemoveClient = (clientId: number) => {
        const tg = window.Telegram?.WebApp;

        const confirmRemove = () => {
            if (selectedClient && selectedClient.id === clientId) {
                setSelectedClient(null);
            }
            removeClient(clientId);
        };

        if (tg?.showConfirm) {
            tg.showConfirm('Удалить клиента из списка?', (confirmed: boolean) => {
                if (confirmed) confirmRemove();
            });
        } else if (window.confirm('Удалить клиента из списка?')) {
            confirmRemove();
        }
    };

    const handleOpenChat = (username: string) => {
        if (username && username !== 'anon') {
            const tg = window.Telegram?.WebApp;
            if (tg?.openTelegramLink) {
                tg.openTelegramLink(`https://t.me/${username}`);
            } else {
                window.open(`https://t.me/${username}`, '_blank');
            }
        }
    };

    if (selectedClient) {
        const activityInfo = ACTIVITY_DESCRIPTIONS[selectedClient.details.activity_level] || {
            title: selectedClient.details.activity_level,
            description: '',
            icon: '❓'
        };

        const trainingInfo = TRAINING_LEVEL_DESCRIPTIONS[selectedClient.details.training_level] || {
            title: selectedClient.details.training_level,
            description: '',
            icon: '💪',
            color: 'text-gray-500'
        };

        return (
            <div className="space-y-4 pb-20">
                <div className="flex items-center justify-between mb-4">
                    <button onClick={() => setSelectedClient(null)} className="p-2 -ml-2 text-gray-600">
                        <ArrowLeft size={24} />
                    </button>
                    <h1 className="text-xl font-bold">Профиль клиента</h1>
                    <div className="w-8"></div>
                </div>

                <div className="bg-blue-500 text-white p-6 rounded-2xl shadow-lg flex items-center gap-4">
                    <div className="w-16 h-16 bg-white/20 rounded-full overflow-hidden">
                        <Avatar
                            src={selectedClient.photo_url}
                            alt={selectedClient.first_name}
                            className="w-full h-full rounded-full object-cover"
                        />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold">{selectedClient.first_name}</h2>
                        <p className="opacity-90">@{selectedClient.username}</p>
                    </div>
                </div>

                <button
                    onClick={() => handleOpenChat(selectedClient.username)}
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
                            <div className="font-bold text-gray-900 text-right">{selectedClient.details.age} лет</div>
                        </div>
                        <InfoItem label="Пол:" value={selectedClient.details.gender} />
                        <InfoItem label="Рост:" value={`${selectedClient.details.height} см`} />
                        <InfoItem label="Вес:" value={`${selectedClient.details.weight} кг`} />
                        <InfoItem label="Целевой вес:" value={`${selectedClient.details.target_weight} кг`} />
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
                                    {selectedClient.details.goals.map((goal, index) => (
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
                                    {selectedClient.details.limitations.map((limitation, index) => (
                                        <div key={index} className="flex items-center gap-2">
                                            <CheckCircle2 size={18} className="text-red-500 shrink-0" />
                                            <span className="text-gray-900 font-medium">{limitation}</span>
                                        </div>
                                    ))}
                                    {selectedClient.details.limitations.length === 0 && (
                                        <div className="text-gray-500 italic">Нет ограничений</div>
                                    )}
                                </div>
                            </div>

                            <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                                <div className="text-sm text-gray-500 mb-3">Тип фигуры</div>
                                <div className="flex flex-col gap-3">
                                    <div className="aspect-[3/4] w-full max-w-[200px] bg-gray-200 rounded-lg overflow-hidden self-center">
                                        {selectedClient.details.body_type.image_url ? (
                                            <img
                                                src={selectedClient.details.body_type.image_url}
                                                alt={selectedClient.details.body_type.description}
                                                className="w-full h-full object-cover"
                                            />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center text-gray-400">
                                                <ImageIcon size={48} />
                                            </div>
                                        )}
                                    </div>
                                    <div className="text-center">
                                        <div className="font-bold text-gray-900">{selectedClient.details.body_type.description}</div>
                                    </div>
                                </div>
                            </div>

                            <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                                <div className="text-sm text-gray-500 mb-3">Желаемая форма</div>
                                <div className="flex flex-col gap-3">
                                    <div className="aspect-[3/4] w-full max-w-[200px] bg-gray-200 rounded-lg overflow-hidden self-center">
                                        {selectedClient.details.desired_body_type.image_url ? (
                                            <img
                                                src={selectedClient.details.desired_body_type.image_url}
                                                alt={selectedClient.details.desired_body_type.description}
                                                className="w-full h-full object-cover"
                                            />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center text-gray-400">
                                                <ImageIcon size={48} />
                                            </div>
                                        )}
                                    </div>
                                    <div className="text-center">
                                        <div className="font-bold text-gray-900">{selectedClient.details.desired_body_type.description}</div>
                                    </div>
                                </div>
                            </div>

                            <div className="bg-white p-4 rounded-xl border border-gray-100">
                                <div className="text-sm text-gray-500 mb-2">Часовой пояс</div>
                                <div className="bg-gray-50 p-3 rounded-lg text-center">
                                    <div className="font-bold text-gray-900 text-lg">{selectedClient.details.timezone}</div>
                                </div>
                            </div>

                            {/* Delete Button */}
                            <div className="pt-4 border-t border-gray-100">
                                <button
                                    onClick={() => handleRemoveClient(selectedClient.id)}
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
    }

    return (
        <div className="space-y-6 pb-20">
            <div className="flex items-center justify-between">
                <button onClick={() => navigate('/admin')} className="p-2 -ml-2 text-gray-600">
                    <ArrowLeft size={24} />
                </button>
                <h1 className="text-xl font-bold">Мои клиенты</h1>
                <div className="w-8"></div>
            </div>

            <button
                onClick={() => navigate('/admin/invite-client')}
                className="w-full bg-blue-500 text-white py-4 rounded-2xl font-bold text-base flex items-center justify-center gap-2 shadow-lg active:scale-98 transition-transform"
            >
                <UserPlus size={22} />
                Пригласить клиента
            </button>

            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
                <input
                    type="text"
                    placeholder="Поиск клиентов..."
                    className="w-full bg-white border border-gray-200 rounded-xl pl-10 pr-4 py-3 text-sm focus:outline-none focus:border-blue-500 transition-colors"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                />
            </div>

            <div className="space-y-3">
                {filteredClients.map(client => (
                    <div key={client.id} className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100">
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
                                onClick={() => setSelectedClient(client)}
                                className="flex-1 bg-blue-500 text-white py-2.5 rounded-xl font-medium text-sm flex items-center justify-center gap-2 active:scale-95 transition-transform"
                            >
                                <Eye size={18} />
                                Подробнее
                            </button>
                            <button
                                onClick={() => handleOpenChat(client.username)}
                                className="w-10 flex items-center justify-center bg-blue-50 text-blue-500 rounded-xl active:scale-95 transition-transform"
                            >
                                <MessageCircle size={18} />
                            </button>
                        </div>
                    </div>
                ))}

                {filteredClients.length === 0 && (
                    <div className="text-center text-gray-500 py-12">
                        <User size={48} className="mx-auto mb-3 opacity-30" />
                        <p className="font-medium">Клиентов не найдено</p>
                        <p className="text-sm mt-1">Добавьте клиентов из заявок</p>
                    </div>
                )}
            </div>
        </div>
    );
};

const InfoItem: React.FC<{ label: string; value: string | number }> = ({ label, value }) => (
    <div className="bg-gray-50 p-3 rounded-xl flex flex-col">
        <div className="text-xs text-gray-500 mb-1">{label}</div>
        <div className="font-bold text-gray-900 text-right">{value}</div>
    </div>
);

export default ClientsPage;
