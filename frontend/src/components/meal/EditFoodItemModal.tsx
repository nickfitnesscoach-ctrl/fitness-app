import React from 'react';
import { Edit2 } from 'lucide-react';

interface EditFoodItemModalProps {
    isOpen: boolean;
    onClose: () => void;
    onConfirm: () => void;
    loading: boolean;
    itemName: string;
    itemGrams: string;
    onNameChange: (name: string) => void;
    onGramsChange: (grams: string) => void;
}

export const EditFoodItemModal: React.FC<EditFoodItemModalProps> = ({
    isOpen,
    onClose,
    onConfirm,
    loading,
    itemName,
    itemGrams,
    onNameChange,
    onGramsChange,
}) => {
    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-3xl p-6 max-w-sm w-full shadow-2xl">
                <div className="mb-4">
                    <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-3">
                        <Edit2 className="text-blue-600" size={32} />
                    </div>
                    <h3 className="text-xl font-bold text-gray-900 text-center mb-2">
                        Редактировать блюдо
                    </h3>
                </div>

                <div className="space-y-4 mb-6">
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Название
                        </label>
                        <input
                            type="text"
                            value={itemName}
                            onChange={(e) => onNameChange(e.target.value)}
                            className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                            placeholder="Название блюда"
                        />
                    </div>
                    <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                            Вес (граммы)
                        </label>
                        <input
                            type="number"
                            value={itemGrams}
                            onChange={(e) => onGramsChange(e.target.value)}
                            className="w-full border border-gray-300 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all"
                            placeholder="Вес в граммах"
                            min="1"
                            max="10000"
                        />
                    </div>
                </div>

                <div className="space-y-3">
                    <button
                        onClick={onConfirm}
                        disabled={loading}
                        className="w-full bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-xl font-bold transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {loading ? 'Сохранение...' : 'Сохранить'}
                    </button>
                    <button
                        onClick={onClose}
                        disabled={loading}
                        className="w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-3 rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        Отмена
                    </button>
                </div>
            </div>
        </div>
    );
};
