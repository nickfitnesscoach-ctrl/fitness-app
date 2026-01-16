import React from 'react';
import { Trash2 } from 'lucide-react';
import { useBodyScrollLock } from '../../hooks/useBodyScrollLock';

interface DeleteMealModalProps {
    open: boolean;
    deleting: boolean;
    onConfirm: () => void;
    onCancel: () => void;
}

export const DeleteMealModal: React.FC<DeleteMealModalProps> = ({
    open,
    deleting,
    onConfirm,
    onCancel
}) => {
    useBodyScrollLock(open);

    if (!open) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-3xl p-6 max-w-sm w-full shadow-2xl">
                <div className="text-center mb-4">
                    <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-3">
                        <Trash2 className="text-red-600" size={32} />
                    </div>
                    <h3 className="text-xl font-bold text-gray-900 mb-2">
                        Удалить приём пищи?
                    </h3>
                    <p className="text-gray-600">
                        Это действие нельзя будет отменить. Все блюда в этом приёме пищи будут удалены.
                    </p>
                </div>

                <div className="space-y-3">
                    <button
                        onClick={onConfirm}
                        disabled={deleting}
                        className="w-full bg-red-600 hover:bg-red-700 text-white py-3 rounded-xl font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {deleting ? 'Удаление...' : 'Да, удалить'}
                    </button>
                    <button
                        onClick={onCancel}
                        disabled={deleting}
                        className="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-3 rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Отмена
                    </button>
                </div>
            </div>
        </div>
    );
};
