import { useEffect, useState } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { ClipboardList, Users, LayoutDashboard } from 'lucide-react';

const Layout = () => {
    const [isTelegramWebApp, setIsTelegramWebApp] = useState<boolean | null>(null);
    const [authState, setAuthState] = useState<{
        status: 'loading' | 'authorized' | 'forbidden' | 'error';
        message?: string | null;
        userId?: number | null;
    }>({
        status: 'loading',
        message: null,
        userId: null,
    });

    useEffect(() => {
        let isMounted = true;

        const authorize = async () => {
            const tg = (window as any).Telegram?.WebApp;
            const hasWebApp = Boolean(tg);
            if (isMounted) {
                setIsTelegramWebApp(hasWebApp);
            }

            if (!hasWebApp) {
                return;
            }

            tg.ready();
            const initData = tg?.initData || '';
            console.log('TG WebApp:', !!tg, 'initData length:', initData?.length);

            if (!initData) {
                if (isMounted) {
                    setAuthState({ status: 'error', message: 'Не удалось получить данные Telegram', userId: null });
                }
                return;
            }

            try {
                const response = await fetch('/api/v1/trainer-panel/auth/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ init_data: initData }),
                });

                if (response.status === 200) {
                    const data = await response.json();
                    if (isMounted) {
                        setAuthState({ status: 'authorized', message: null, userId: data.user_id });
                    }
                    return;
                }

                if (response.status === 401 || response.status === 403) {
                    if (isMounted) {
                        setAuthState({ status: 'forbidden', message: 'У вас нет прав доступа', userId: null });
                    }
                    return;
                }

                const errorData = await response.json().catch(() => ({}));
                if (isMounted) {
                    setAuthState({
                        status: 'error',
                        message: (errorData as { detail?: string }).detail || 'Ошибка авторизации',
                        userId: null,
                    });
                }
            } catch (error) {
                console.error('[TrainerPanel] Auth failed', error);
                if (isMounted) {
                    setAuthState({ status: 'error', message: 'Ошибка авторизации', userId: null });
                }
            }
        };

        authorize();

        return () => {
            isMounted = false;
        };
    }, []);

    if (isTelegramWebApp === null) {
        return (
            <div className="no-access">
                <h1>Загрузка...</h1>
                <p>Проверяем доступ через Telegram.</p>
            </div>
        );
    }

    if (isTelegramWebApp === false) {
        return (
            <div className="no-access">
                <h1>Нет доступа</h1>
                <p>Панель тренера доступна только из Telegram-бота.</p>
                <p>Откройте бота и нажмите «📱 Открыть панель тренера».</p>
            </div>
        );
    }

    if (authState.status === 'loading') {
        return (
            <div className="no-access">
                <h1>Загрузка...</h1>
                <p>Проверяем доступ через Telegram.</p>
            </div>
        );
    }

    if (authState.status === 'forbidden') {
        return (
            <div className="no-access">
                <h1>Нет прав доступа</h1>
                <p>У вас нет прав доступа к панели тренера.</p>
            </div>
        );
    }

    if (authState.status === 'error') {
        return (
            <div className="no-access">
                <h1>Нет доступа</h1>
                <p>{authState.message || 'Произошла ошибка при авторизации.'}</p>
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
