import React, { useState, useEffect } from 'react';
import { Search, Copy, Eye, MessageCircle, UserPlus, ArrowLeft, User, CheckCircle2, AlertCircle, ImageIcon } from 'lucide-react';
import { Application } from '../services/mockData';
import { useClients } from '../contexts/ClientsContext';
import { api } from '../services/api';
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

// Helper Component for Basic Info Grid
const InfoItem: React.FC<{ label: string; value: string | number }> = ({ label, value }) => (
    <div className="bg-gray-50 p-3 rounded-xl flex flex-col">
        <div className="text-xs text-gray-500 mb-1">{label}</div>
        <div className="font-bold text-gray-900 text-right">{value}</div>
    </div>
);

const ApplicationsPage: React.FC = () => {
    const navigate = useNavigate();
    const { addClient, isClient } = useClients();
    const [selectedApp, setSelectedApp] = useState<Application | null>(null);
    const [searchTerm, setSearchTerm] = useState('');
    const [filterStatus, setFilterStatus] = useState<'all' | 'new' | 'viewed' | 'contacted'>('new');

    // State for real data
    const [applications, setApplications] = useState<Application[]>([]);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const loadData = async () => {
            setIsLoading(true);
            try {
                const data = await api.getApplications();

                // Map backend data to frontend Application interface
                const genderMap: Record<string, string> = {
                    'male': 'Мужской',
                    'female': 'Женский'
                };
                const activityMap: Record<string, string> = {
                    'minimal': 'Минимальная',
                    'low': 'Низкая',
                    'medium': 'Средняя',
                    'high': 'Высокая'
                };
                const trainingMap: Record<string, string> = {
                    'beginner': 'Новичок',
                    'intermediate': 'Средний',
                    'advanced': 'Продвинутый',
                    'home': 'Домашний формат'
                };
                const goalsMap: Record<string, string> = {
                    'weight_loss': 'Снижение веса',
                    'fat_loss': 'Сжигание жира',
                    'muscle_gain': 'Набор мышц',
                    'tighten_body': 'Подтянуть тело',
                    'belly_sides': 'Убрать живот и бока',
                    'glutes_shape': 'Округлые ягодицы',
                    'maintenance': 'Поддержание формы'
                };
                const restrictionsMap: Record<string, string> = {
                    'none': 'Нет ограничений',
                    'back': 'Проблемы со спиной',
                    'joints': 'Проблемы с суставами',
                    'heart': 'Сердечно-сосудистые',
                    'allergy': 'Аллергии',
                    'stress': 'Высокий стресс',
                    'diabetes': 'Диабет'
                };

                const formattedData: Application[] = data.map((item: any) => {
                    const details = item.details || {};
                    return {
                        id: item.id,
                        first_name: item.first_name,
                        username: item.username || 'anon',
                        photo_url: item.photo_url || '',
                        status: item.status || 'new',
                        date: new Date(item.created_at).toLocaleDateString('ru-RU'),
                        details: {
                            age: details.age || 0,
                            gender: genderMap[details.gender] || 'Не указан',
                            height: details.height || 0,
                            weight: details.weight || 0,
                            target_weight: details.target_weight || 0,
                            activity_level: activityMap[details.activity_level] || 'Не указана',
                            training_level: trainingMap[details.training_level] || 'Не указан',
                            goals: (details.goals || []).map((g: string) => goalsMap[g] || g),
                            limitations: (details.health_restrictions || []).map((r: string) => restrictionsMap[r] || r),
                            body_type: {
                                id: details.current_body_type || 1,
                                description: 'Текущая форма',
                                image_url: details.current_body_type ? `/assets/body_types/${details.gender === 'male' ? 'm' : 'f'}_type_${details.current_body_type}.jpg` : ''
                            },
                            desired_body_type: {
                                id: details.ideal_body_type || 1,
                                description: 'Желаемая форма',
                                image_url: details.ideal_body_type ? `/assets/body_types/${details.gender === 'male' ? 'm' : 'f'}_type_after_${details.ideal_body_type}.jpg` : ''
                            },
                            timezone: details.timezone || 'UTC+3'
                        }
                    };
                });
                setApplications(formattedData);
            } catch (error) {
                console.error("Failed to load applications", error);
                // Fallback to mock data if API fails (optional, for dev)
                // setApplications(MOCK_APPLICATIONS); 
            } finally {
                setIsLoading(false);
            }
        };

        loadData();
    }, []);

    const filteredApps = applications
        .filter(app => !isClient(app.id)) // Hide if already a client
        .filter(app => {
            const matchesSearch = app.first_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
                app.username.toLowerCase().includes(searchTerm.toLowerCase());
            const matchesStatus = filterStatus === 'all' || app.status === filterStatus;
            return matchesSearch && matchesStatus;
        });

    const handleMakeClient = () => {
        if (selectedApp) {
            addClient(selectedApp);
            setSelectedApp(null);
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

    const handleChangeStatus = async (appId: number, newStatus: 'new' | 'viewed' | 'contacted') => {
        try {
            // Сначала обновляем UI (optimistic update)
            setApplications(prev => prev.map(app =>
                app.id === appId ? { ...app, status: newStatus } : app
            ));
            // Также обновляем selectedApp если он открыт
            if (selectedApp && selectedApp.id === appId) {
                setSelectedApp({ ...selectedApp, status: newStatus });
            }
            // Сохраняем в базу данных
            await api.updateApplicationStatus(appId, newStatus);
        } catch (error) {
            console.error('Ошибка при обновлении статуса:', error);
        }
    };

    const handleDeleteApplication = async (appId: number) => {
        // Показываем подтверждение через Telegram WebApp или стандартный confirm
        const tg = window.Telegram?.WebApp;
        const confirmDelete = async () => {
            try {
                // Удаляем из базы данных
                await api.deleteApplication(appId);
                // Удаляем из локального состояния
                setApplications(prev => prev.filter(app => app.id !== appId));
                setSelectedApp(null);
            } catch (error) {
                console.error('Ошибка при удалении:', error);
                // Можно показать уведомление об ошибке
                if (tg?.showAlert) {
                    tg.showAlert('Не удалось удалить заявку. Попробуйте позже.');
                } else {
                    alert('Не удалось удалить заявку. Попробуйте позже.');
                }
            }
        };

        if (tg?.showConfirm) {
            tg.showConfirm('Удалить эту заявку? Это действие нельзя отменить.', (confirmed: boolean) => {
                if (confirmed) confirmDelete();
            });
        } else if (window.confirm('Удалить эту заявку? Это действие нельзя отменить.')) {
            confirmDelete();
        }
    };

    if (selectedApp) {
        const activityInfo = ACTIVITY_DESCRIPTIONS[selectedApp.details.activity_level] || {
            title: selectedApp.details.activity_level,
            description: '',
            icon: '❓'
        };

        const trainingInfo = TRAINING_LEVEL_DESCRIPTIONS[selectedApp.details.training_level] || {
            title: selectedApp.details.training_level,
            description: '',
            icon: '💪',
            color: 'text-gray-500'
        };

        return (
            <div className="space-y-4 pb-20">
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                    <button onClick={() => setSelectedApp(null)} className="p-2 -ml-2 text-gray-600">
                        <ArrowLeft size={24} />
                    </button>
                    <h1 className="text-xl font-bold">Результаты опроса</h1>
                    <div className="w-8"></div> {/* Spacer for centering */}
                </div>

                {/* Profile Card */}
                <div className="bg-blue-500 text-white p-6 rounded-2xl shadow-lg flex items-center gap-4">
                    <div className="w-16 h-16 bg-white/20 rounded-full overflow-hidden">
                        <Avatar
                            src={selectedApp.photo_url}
                            alt={selectedApp.first_name}
                            className="w-full h-full rounded-full object-cover"
                        />
                    </div>
                    <div>
                        <h2 className="text-2xl font-bold">{selectedApp.first_name}</h2>
                        <p className="opacity-90">@{selectedApp.username}</p>
                    </div>
                </div>

                {/* Action Buttons */}
                <div className="grid grid-cols-2 gap-3">
                    <button
                        onClick={() => handleOpenChat(selectedApp.username)}
                        className="flex items-center justify-center gap-2 bg-white border border-gray-200 py-3 rounded-xl font-medium text-gray-700 shadow-sm active:scale-95 transition-transform"
                    >
                        <MessageCircle size={20} />
                        Написать в чат
                    </button>
                    <button
                        onClick={handleMakeClient}
                        className="flex items-center justify-center gap-2 bg-blue-500 text-white py-3 rounded-xl font-medium shadow-sm active:scale-95 transition-transform"
                    >
                        <UserPlus size={20} />
                        Сделать клиентом
                    </button>
                </div>

                {/* Hint */}
                <div className="bg-gray-50 p-3 rounded-lg border border-gray-100 text-xs text-gray-500">
                    Если не получается перейти в чат с клиентом, выполните поиск контакта по его username <span className="text-blue-600 font-medium">@{selectedApp.username}</span>
                </div>

                {/* Status Change Buttons */}
                <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4">
                    <h3 className="font-bold text-sm mb-3 text-gray-700">Изменить статус заявки:</h3>
                    <div className="flex gap-2">
                        <button
                            onClick={() => handleChangeStatus(selectedApp.id, 'new')}
                            className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all ${
                                selectedApp.status === 'new'
                                    ? 'bg-blue-500 text-white'
                                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                        >
                            Новая
                        </button>
                        <button
                            onClick={() => handleChangeStatus(selectedApp.id, 'viewed')}
                            className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all ${
                                selectedApp.status === 'viewed'
                                    ? 'bg-yellow-500 text-white'
                                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                            }`}
                        >
                            Просмотрено
                        </button>
                        <button
                            onClick={() => handleChangeStatus(selectedApp.id, 'contacted')}
                            className={`flex-1 py-2 px-3 rounded-lg text-sm font-medium transition-all ${
                                selectedApp.status === 'contacted'
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
                            <div className="font-bold text-gray-900 text-right">{selectedApp.details.age} лет</div>
                        </div>
                        <InfoItem label="Пол:" value={selectedApp.details.gender} />
                        <InfoItem label="Рост:" value={`${selectedApp.details.height} см`} />
                        <InfoItem label="Вес:" value={`${selectedApp.details.weight} кг`} />
                        <InfoItem label="Целевой вес:" value={`${selectedApp.details.target_weight} кг`} />
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
                                    {selectedApp.details.goals.map((goal, index) => (
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
                                    {selectedApp.details.limitations.map((limitation, index) => (
                                        <div key={index} className="flex items-center gap-2">
                                            <CheckCircle2 size={18} className="text-red-500 shrink-0" />
                                            <span className="text-gray-900 font-medium">{limitation}</span>
                                        </div>
                                    ))}
                                    {selectedApp.details.limitations.length === 0 && (
                                        <div className="text-gray-500 italic">Нет ограничений</div>
                                    )}
                                </div>
                            </div>

                            {/* Body Type Section */}
                            <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                                <div className="text-sm text-gray-500 mb-3">Тип фигуры</div>
                                <div className="flex flex-col gap-3">
                                    <div className="aspect-[3/4] w-full max-w-[200px] bg-gray-200 rounded-lg overflow-hidden self-center">
                                        {selectedApp.details.body_type.image_url ? (
                                            <img
                                                src={selectedApp.details.body_type.image_url}
                                                alt={selectedApp.details.body_type.description}
                                                className="w-full h-full object-cover"
                                            />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center text-gray-400">
                                                <ImageIcon size={48} />
                                            </div>
                                        )}
                                    </div>
                                    <div className="text-center">
                                        <div className="font-bold text-gray-900">{selectedApp.details.body_type.description}</div>
                                    </div>
                                </div>
                            </div>

                            {/* Desired Body Type Section */}
                            <div className="bg-gray-50 p-4 rounded-xl border border-gray-100">
                                <div className="text-sm text-gray-500 mb-3">Желаемая форма</div>
                                <div className="flex flex-col gap-3">
                                    <div className="aspect-[3/4] w-full max-w-[200px] bg-gray-200 rounded-lg overflow-hidden self-center">
                                        {selectedApp.details.desired_body_type.image_url ? (
                                            <img
                                                src={selectedApp.details.desired_body_type.image_url}
                                                alt={selectedApp.details.desired_body_type.description}
                                                className="w-full h-full object-cover"
                                            />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center text-gray-400">
                                                <ImageIcon size={48} />
                                            </div>
                                        )}
                                    </div>
                                    <div className="text-center">
                                        <div className="font-bold text-gray-900">{selectedApp.details.desired_body_type.description}</div>
                                    </div>
                                </div>
                            </div>

                            {/* Timezone Section */}
                            <div className="bg-white p-4 rounded-xl border border-gray-100">
                                <div className="text-sm text-gray-500 mb-2">Часовой пояс</div>
                                <div className="bg-gray-50 p-3 rounded-lg text-center">
                                    <div className="font-bold text-gray-900 text-lg">{selectedApp.details.timezone}</div>
                                </div>
                            </div>

                            {/* Delete Button */}
                            <div className="pt-4 border-t border-gray-100">
                                <button
                                    onClick={() => handleDeleteApplication(selectedApp.id)}
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
    }

    return (
        <div className="space-y-6 pb-20">
            {/* Header */}
            <div className="flex items-center justify-between">
                <button onClick={() => navigate('/admin')} className="p-2 -ml-2 text-gray-600">
                    <ArrowLeft size={24} />
                </button>
                <h1 className="text-xl font-bold">Мои заявки</h1>
                <div className="w-8"></div> {/* Spacer */}
            </div>

            {/* Lead Magnet Link */}
            <div className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100 space-y-3">
                <h3 className="font-bold text-gray-900">Ссылка на Лид-магнит</h3>
                <p className="text-sm text-gray-500">Разместите ее в своих соц.сетях</p>
                <div className="flex gap-2">
                    <div className="bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 text-xs text-gray-600 flex-1 truncate font-mono">
                        https://t.me/nick_fitness_test_bot
                    </div>
                    <button
                        onClick={() => {
                            navigator.clipboard.writeText('https://t.me/nick_fitness_test_bot');
                            const tg = window.Telegram?.WebApp;
                            if (tg?.showAlert) {
                                tg.showAlert('Ссылка скопирована!');
                            }
                        }}
                        className="bg-gray-100 hover:bg-gray-200 p-2 rounded-lg transition-colors"
                    >
                        <Copy size={18} className="text-gray-600" />
                    </button>
                </div>
            </div>

            {/* Search */}
            <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" size={20} />
                <input
                    type="text"
                    placeholder="Поиск заявок..."
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                    className="w-full bg-white pl-10 pr-4 py-3 rounded-xl border-none shadow-sm focus:ring-2 focus:ring-blue-500 outline-none"
                />
            </div>

            {/* Filter Tabs */}
            <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-hide">
                {(['all', 'new', 'viewed', 'contacted'] as const).map((status) => (
                    <button
                        key={status}
                        onClick={() => setFilterStatus(status)}
                        className={`px-4 py-2 rounded-full text-sm font-medium whitespace-nowrap transition-colors ${filterStatus === status
                                ? 'bg-blue-500 text-white'
                                : 'bg-white text-gray-600 hover:bg-gray-50'
                            }`}
                    >
                        {status === 'all' && 'Все'}
                        {status === 'new' && 'Новые'}
                        {status === 'viewed' && 'Просмотренные'}
                        {status === 'contacted' && 'Связался'}
                    </button>
                ))}
            </div>

            {/* Applications List */}
            <div className="space-y-3">
                {isLoading ? (
                    <div className="text-center py-10 text-gray-500">Загрузка заявок...</div>
                ) : filteredApps.length > 0 ? (
                    filteredApps.map((app) => (
                        <div
                            key={app.id}
                            className="bg-white p-4 rounded-2xl shadow-sm border border-gray-100"
                        >
                            <div className="flex items-start gap-3 mb-3">
                                <div className="w-12 h-12 bg-gray-100 rounded-full overflow-hidden">
                                    <Avatar
                                        src={app.photo_url}
                                        alt={app.first_name}
                                        className="w-full h-full rounded-full object-cover"
                                    />
                                </div>
                                <div className="flex-1">
                                    <div className="flex items-center justify-between">
                                        <h3 className="font-bold text-gray-900">{app.first_name}</h3>
                                        {app.status === 'new' && (
                                            <span className="bg-blue-100 text-blue-600 text-[10px] font-bold px-2 py-1 rounded-full">
                                                НОВАЯ
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-sm text-gray-500">@{app.username}</p>
                                </div>
                            </div>

                            <div className="grid grid-cols-4 gap-2 mb-3 bg-gray-50 p-3 rounded-lg">
                                <div className="text-center">
                                    <div className="text-xs text-gray-500">Возраст</div>
                                    <div className="font-bold text-gray-900">{app.details.age}</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-xs text-gray-500">Вес</div>
                                    <div className="font-bold text-gray-900">{app.details.weight} кг</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-xs text-gray-500">Пол</div>
                                    <div className="font-bold text-gray-900">{app.details.gender === 'Мужской' ? 'М' : 'Ж'}</div>
                                </div>
                                <div className="text-center">
                                    <div className="text-xs text-gray-500">Акт.</div>
                                    <div className="font-bold text-gray-900 text-xs">{app.details.activity_level.substring(0, 3)}</div>
                                </div>
                            </div>

                            <div className="flex gap-2">
                                <button
                                    onClick={() => setSelectedApp(app)}
                                    className="flex-1 bg-blue-500 text-white py-2.5 rounded-xl font-medium text-sm flex items-center justify-center gap-2 active:scale-95 transition-transform"
                                >
                                    <Eye size={18} />
                                    Подробнее
                                </button>
                                <button
                                    onClick={() => handleOpenChat(app.username)}
                                    className="w-10 flex items-center justify-center bg-blue-50 text-blue-500 rounded-xl active:scale-95 transition-transform"
                                >
                                    <MessageCircle size={18} />
                                </button>
                            </div>
                        </div>
                    ))
                ) : (
                    <div className="text-center py-10 text-gray-500">
                        Нет заявок, соответствующих фильтрам
                    </div>
                )}
            </div>
        </div>
    );
};

export default ApplicationsPage;
