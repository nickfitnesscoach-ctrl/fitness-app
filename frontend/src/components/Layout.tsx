import { useEffect, useMemo, useState } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { ClipboardList, Users, LayoutDashboard } from 'lucide-react';
import { initTelegramWebApp, isTelegramWebAppAvailable } from '../lib/telegram';
import { api } from '../services/api';

const Layout = () => {
    const isTelegramContext = useMemo(() => isTelegramWebAppAvailable(), []);
    const [authState, setAuthState] = useState<{
        loading: boolean;
        error: string | null;
        userId: number | null;
    }>({
        loading: true,
        error: null,
        userId: null,
    });

    useEffect(() => {
        let isMounted = true;

        const authorize = async () => {
            // Быстро отсекаем прямые заходы
            if (!isTelegramWebAppAvailable()) {
                if (isMounted) {
                    setAuthState({ loading: false, error: 'Нет доступа', userId: null });
                }
                return;
            }

            const tgData = await initTelegramWebApp();
            if (!tgData) {
                if (isMounted) {
                    setAuthState({ loading: false, error: 'Нет доступа', userId: null });
                }
                return;
            }

            try {
                const response = await api.trainerPanelAuth(tgData.initData);
                if (isMounted) {
                    setAuthState({ loading: false, error: null, userId: response.user_id });
                }
            } catch (error) {
                console.error('[TrainerPanel] Auth failed', error);
                if (isMounted) {
                    setAuthState({ loading: false, error: 'Нет доступа', userId: null });
                }
            }
        };

        authorize();

        return () => {
            isMounted = false;
        };
    }, []);

    if (!isTelegramContext) {
        return (
            <div className="no-access">
                <h1>Нет доступа</h1>
                <p>Панель тренера доступна только из Telegram-бота.</p>
                <p>Откройте бота и нажмите «📱 Открыть панель тренера».</p>
            </div>
        );
    }

    if (authState.loading) {
        return (
            <div className="no-access">
                <h1>Загрузка...</h1>
                <p>Проверяем доступ через Telegram.</p>
            </div>
        );
    }

    if (authState.error) {
        return (
            <div className="no-access">
                <h1>Нет доступа</h1>
                <p>Панель тренера доступна только из Telegram-бота.</p>
                <p>Откройте бота и нажмите «📱 Открыть панель тренера».</p>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gray-50 flex flex-col">
            <main className="flex-1 p-4 overflow-y-auto">
                <Outlet />
            </main>

            <nav className="bg-white border-t border-gray-200 px-6 py-3 flex justify-around items-center shadow-lg z-10">
                <NavLink
                    to="/panel"
                    className={({ isActive }) =>
                        `flex flex-col items-center gap-1 text-xs font-medium transition-colors ${isActive ? 'text-blue-600' : 'text-gray-500 hover:text-gray-700'
                        }`
                    }
                >
                    <LayoutDashboard size={24} />
                    <span>Главная</span>
                </NavLink>

                <NavLink
                    to="/panel/applications"
                    className={({ isActive }) =>
                        `flex flex-col items-center gap-1 text-xs font-medium transition-colors ${isActive ? 'text-blue-600' : 'text-gray-500 hover:text-gray-700'
                        }`
                    }
                >
                    <ClipboardList size={24} />
                    <span>Заявки</span>
                </NavLink>

                <NavLink
                    to="/panel/clients"
                    className={({ isActive }) =>
                        `flex flex-col items-center gap-1 text-xs font-medium transition-colors ${isActive ? 'text-blue-600' : 'text-gray-500 hover:text-gray-700'
                        }`
                    }
                >
                    <Users size={24} />
                    <span>Клиенты</span>
                </NavLink>
            </nav>
        </div>
    );
};

export default Layout;
