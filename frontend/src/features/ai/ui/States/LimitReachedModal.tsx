import React from 'react';
import { AlertCircle, CreditCard } from 'lucide-react';
import { useBodyScrollLock } from '../../../../hooks/useBodyScrollLock';

interface LimitReachedModalProps {
    dailyLimit: number;
    onClose: () => void;
    onUpgrade: () => void;
    /** Controls scroll lock (required for proper iOS scroll lock lifecycle). */
    isOpen: boolean;
}

/**
 * Modal shown when daily photo limit is reached
 */
export const LimitReachedModal: React.FC<LimitReachedModalProps> = ({
    dailyLimit,
    onClose,
    onUpgrade,
    isOpen,
}) => {
    useBodyScrollLock(isOpen);

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-3xl p-6 max-w-sm w-full shadow-2xl">
                <div className="text-center mb-4">
                    <AlertCircle className="text-red-500 mx-auto mb-3" size={48} />
                    <h3 className="text-xl font-bold text-gray-900 mb-2">
                        Лимит исчерпан
                    </h3>
                    <p className="text-gray-600">
                        Вы использовали свои {dailyLimit} бесплатных анализа.
                        Некоторые фото не были обработаны.
                    </p>
                </div>

                <div className="space-y-3">
                    <button
                        onClick={onUpgrade}
                        className="w-full bg-gradient-to-r from-blue-500 to-purple-500 text-white py-3 rounded-xl font-bold hover:from-blue-600 hover:to-purple-600 transition-colors flex items-center justify-center gap-2"
                    >
                        <CreditCard size={20} />
                        Оформить PRO
                    </button>
                    <button
                        onClick={onClose}
                        className="w-full bg-gray-200 text-gray-700 py-3 rounded-xl font-medium hover:bg-gray-300 transition-colors"
                    >
                        Понятно
                    </button>
                </div>
            </div>
        </div>
    );
};
