/**
 * AuthErrorModal - Глобальный обработчик ошибок авторизации
 * 
 * Подписывается на события auth:error из api.ts и показывает модалку
 * с предложением перезапустить приложение через Telegram.
 */

import { useState, useEffect } from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import { onAuthError, AuthErrorEvent } from '../services/api';
import { closeTelegramWebApp, getTelegramWebApp } from '../lib/telegram';
import { useBodyScrollLock } from '../hooks/useBodyScrollLock';

export const AuthErrorModal: React.FC = () => {
    const [error, setError] = useState<AuthErrorEvent | null>(null);
    const [isVisible, setIsVisible] = useState(false);

    useBodyScrollLock(isVisible);

    useEffect(() => {
        // Подписываемся на auth errors
        const unsubscribe = onAuthError((event) => {
            setError(event);
            setIsVisible(true);
        });

        return unsubscribe;
    }, []);

    const handleReopen = () => {
        // Пытаемся закрыть WebApp - пользователь откроет его заново
        const tg = getTelegramWebApp();
        if (tg) {
            closeTelegramWebApp();
        } else {
            // Если не в Telegram - просто перезагружаем страницу
            window.location.reload();
        }
    };

    const handleDismiss = () => {
        setIsVisible(false);
        setError(null);
    };

    if (!isVisible || !error) {
        return null;
    }

    const isSessionExpired = error.type === 'session_expired';
    const title = isSessionExpired ? 'Сессия истекла' : 'Ошибка доступа';

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-[100]">
            <div className="bg-white rounded-3xl p-6 max-w-sm w-full shadow-2xl animate-in fade-in zoom-in duration-200">
                <div className="text-center mb-4">
                    <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
                        <AlertCircle className="text-red-600" size={32} />
                    </div>
                    <h3 className="text-xl font-bold text-gray-900 mb-2">
                        {title}
                    </h3>
                    <p className="text-gray-600">
                        {error.message}
                    </p>
                    {error.status && (
                        <p className="text-gray-400 text-sm mt-2">
                            Код ошибки: {error.status}
                        </p>
                    )}
                </div>

                <div className="space-y-3">
                    <button
                        onClick={handleReopen}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-xl font-bold transition-colors flex items-center justify-center gap-2"
                    >
                        <RefreshCw size={20} />
                        Перезапустить
                    </button>
                    <button
                        onClick={handleDismiss}
                        className="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-3 rounded-xl font-medium transition-colors"
                    >
                        Закрыть
                    </button>
                </div>
            </div>
        </div>
    );
};

export default AuthErrorModal;
