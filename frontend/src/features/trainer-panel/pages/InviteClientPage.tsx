import { useState } from 'react';
import { Copy, Check, ArrowLeft, Send, UserPlus, CheckCircle } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { TRAINER_INVITE_LINK } from '../constants/invite';

const InviteClientPage = () => {
    const navigate = useNavigate();
    const [copied, setCopied] = useState(false);

    const inviteLink = TRAINER_INVITE_LINK;

    const handleCopy = () => {
        navigator.clipboard.writeText(inviteLink);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="space-y-6 pb-20">
            {/* Header */}
            <div className="flex items-center justify-between">
                <button onClick={() => navigate('/panel/clients')} className="p-2 -ml-2 text-gray-600">
                    <ArrowLeft size={24} />
                </button>
                <h1 className="text-xl font-bold">Пригласить клиента</h1>
                <div className="w-8"></div>
            </div>

            {/* Instructions Card */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100 space-y-4">
                <h2 className="font-bold text-lg text-gray-900">Как пригласить клиента</h2>
                <p className="text-sm text-gray-600 leading-relaxed">
                    Отправьте клиенту специальную ссылку для подключения к вашему профилю тренера.
                    После перехода по ссылке клиент будет автоматически добавлен в ваш список.
                </p>

                {/* Invite Link */}
                <div>
                    <label className="text-sm text-gray-500 mb-2 block">Ссылка для приглашения:</label>
                    <div className="flex gap-2">
                        <div className="flex-1 bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-sm text-gray-700 font-mono break-all">
                            {inviteLink}
                        </div>
                        <button
                            onClick={handleCopy}
                            className="bg-blue-500 hover:bg-blue-600 p-3 rounded-xl transition-colors flex items-center justify-center min-w-[48px]"
                        >
                            {copied ? (
                                <Check size={20} className="text-white" />
                            ) : (
                                <Copy size={20} className="text-white" />
                            )}
                        </button>
                    </div>
                    {copied && (
                        <p className="text-sm text-green-600 mt-2 flex items-center gap-1">
                            <Check size={16} />
                            Ссылка скопирована!
                        </p>
                    )}
                </div>
            </div>

            {/* Client Instructions */}
            <div className="bg-white p-6 rounded-2xl shadow-sm border border-gray-100">
                <h3 className="font-bold text-gray-900 mb-4">Инструкция для клиента</h3>
                <div className="space-y-4">
                    <div className="flex gap-3">
                        <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                            <span className="text-blue-600 font-bold text-sm">1</span>
                        </div>
                        <div>
                            <div className="font-medium text-gray-900 flex items-center gap-2">
                                <span>📱</span>
                                Откройте ссылку на смартфоне
                            </div>
                            <p className="text-sm text-gray-600 mt-1">
                                Клиент должен открыть полученную ссылку на своём телефоне
                            </p>
                        </div>
                    </div>

                    <div className="flex gap-3">
                        <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                            <span className="text-blue-600 font-bold text-sm">2</span>
                        </div>
                        <div>
                            <div className="font-medium text-gray-900 flex items-center gap-2">
                                <Send size={16} />
                                Запустите бота в Telegram
                            </div>
                            <p className="text-sm text-gray-600 mt-1">
                                Ссылка откроет Telegram-бота, нужно нажать "Запустить" или "Start"
                            </p>
                        </div>
                    </div>

                    <div className="flex gap-3">
                        <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center flex-shrink-0">
                            <span className="text-blue-600 font-bold text-sm">3</span>
                        </div>
                        <div>
                            <div className="font-medium text-gray-900 flex items-center gap-2">
                                <UserPlus size={16} />
                                Следуйте инструкциям бота
                            </div>
                            <p className="text-sm text-gray-600 mt-1">
                                Бот попросит заполнить анкету и ответить на вопросы
                            </p>
                        </div>
                    </div>

                    <div className="flex gap-3">
                        <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center flex-shrink-0">
                            <CheckCircle size={16} className="text-green-600" />
                        </div>
                        <div>
                            <div className="font-medium text-gray-900 flex items-center gap-2">
                                <span>✅</span>
                                Клиент появится в вашем списке
                            </div>
                            <p className="text-sm text-gray-600 mt-1">
                                После заполнения анкеты клиент автоматически добавится в ваш список
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* Quick Share Buttons (Optional) */}
            <div className="bg-gray-50 p-4 rounded-2xl border border-gray-100">
                <h4 className="font-medium text-gray-700 mb-3 text-sm">Быстрая отправка</h4>
                <div className="grid grid-cols-2 gap-3">
                    <a
                        href={`https://t.me/share/url?url=${encodeURIComponent(inviteLink)}&text=${encodeURIComponent('Присоединяйся к моей программе тренировок!')}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="bg-blue-500 text-white py-3 rounded-xl font-medium text-sm flex items-center justify-center gap-2 active:scale-95 transition-transform"
                    >
                        <Send size={18} />
                        Telegram
                    </a>
                    <button
                        onClick={handleCopy}
                        className="bg-gray-200 text-gray-700 py-3 rounded-xl font-medium text-sm flex items-center justify-center gap-2 active:scale-95 transition-transform"
                    >
                        <Copy size={18} />
                        Копировать
                    </button>
                </div>
            </div>
        </div>
    );
};

export default InviteClientPage;
