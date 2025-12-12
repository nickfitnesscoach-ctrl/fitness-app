import React from 'react';
import { Search, Copy, ArrowLeft } from 'lucide-react';
import { useClients } from '../../../contexts/ClientsContext';
import { useNavigate } from 'react-router-dom';
import { useApplications } from '../hooks/useApplications';
import { ApplicationDetails } from '../components/applications/ApplicationDetails';
import { ApplicationCard } from '../components/applications/ApplicationCard';
import { TRAINER_INVITE_LINK } from '../constants/invite';

const ApplicationsPage: React.FC = () => {
    const navigate = useNavigate();
    const { addClient, isClient } = useClients();

    const {
        filteredApplications,
        isLoading,
        searchTerm,
        filterStatus,
        selectedApp,
        setSearchTerm,
        setFilterStatus,
        selectApp,
        changeStatus,
        deleteApplication,
    } = useApplications({ isClient });

    const handleMakeClient = () => {
        if (selectedApp) {
            addClient(selectedApp);
            selectApp(null);
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

    const confirmAndDelete = async (appId: number) => {
        const tg = window.Telegram?.WebApp;
        const executeDelete = async () => {
            try {
                await deleteApplication(appId);
            } catch (error) {
                console.error('Ошибка при удалении:', error);
                if (tg?.showAlert) {
                    tg.showAlert('Не удалось удалить заявку. Попробуйте позже.');
                } else {
                    alert('Не удалось удалить заявку. Попробуйте позже.');
                }
            }
        };

        if (tg?.showConfirm) {
            tg.showConfirm('Удалить эту заявку? Это действие нельзя отменить.', (confirmed: boolean) => {
                if (confirmed) executeDelete();
            });
        } else if (window.confirm('Удалить эту заявку? Это действие нельзя отменить.')) {
            executeDelete();
        }
    };

    // Render detailed view if an application is selected
    if (selectedApp) {
        return (
            <ApplicationDetails
                application={selectedApp}
                onBack={() => selectApp(null)}
                onMakeClient={handleMakeClient}
                onOpenChat={() => handleOpenChat(selectedApp.username)}
                onChangeStatus={(status) => changeStatus(selectedApp.id, status)}
                onDelete={() => confirmAndDelete(selectedApp.id)}
            />
        );
    }

    // Render list view
    return (
        <div className="space-y-6 pb-20">
            {/* Header */}
            <div className="flex items-center justify-between">
                <button onClick={() => navigate('/panel')} className="p-2 -ml-2 text-gray-600">
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
                        {TRAINER_INVITE_LINK}
                    </div>
                    <button
                        onClick={() => {
                            navigator.clipboard.writeText(TRAINER_INVITE_LINK);
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
                ) : filteredApplications.length > 0 ? (
                    filteredApplications.map((app) => (
                        <ApplicationCard
                            key={app.id}
                            app={app}
                            onOpenDetails={() => selectApp(app)}
                            onOpenChat={() => handleOpenChat(app.username)}
                        />
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
