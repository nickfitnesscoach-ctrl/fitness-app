import React from 'react';

interface BatchProcessingScreenProps {
    current: number;
    total: number;
    onCancel: () => void;
}

/**
 * Processing screen shown during batch photo analysis
 */
export const BatchProcessingScreen: React.FC<BatchProcessingScreenProps> = ({
    current,
    total,
    onCancel
}) => {
    return (
        <div className="space-y-6">
            <div className="bg-white rounded-3xl p-8 shadow-lg text-center">
                {/* Spinner with progress */}
                <div className="relative w-16 h-16 mx-auto mb-4">
                    <div className="absolute inset-0 border-4 border-gray-100 rounded-full"></div>
                    <div className="absolute inset-0 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
                    <div className="absolute inset-0 flex items-center justify-center">
                        <span className="text-sm font-bold text-blue-600">
                            {current}/{total}
                        </span>
                    </div>
                </div>

                <h3 className="text-xl font-bold text-gray-900 mb-2">
                    Обработка фотографий
                </h3>
                <p className="text-gray-600 font-medium">
                    Загружаю {current} из {total}...
                </p>
                <p className="text-gray-400 text-sm mt-4">
                    Пожалуйста, не закрывайте приложение
                </p>

                {/* Cancel Button */}
                <button
                    onClick={onCancel}
                    className="mt-6 w-full bg-gray-200 hover:bg-gray-300 text-gray-700 py-3 rounded-xl font-medium transition-colors"
                >
                    Прекратить анализ
                </button>
            </div>
        </div>
    );
};
