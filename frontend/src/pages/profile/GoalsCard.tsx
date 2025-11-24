import React from 'react';
import { Target } from 'lucide-react';
import { NutritionTargets, Profile } from '../../types/profile';

interface GoalsCardProps {
    profile: Profile;
    targets: NutritionTargets | null;
    onRecalculateByMifflin: () => void;
    isRecalculating?: boolean;
}

export const GoalsCard: React.FC<GoalsCardProps> = ({ profile, targets, onRecalculateByMifflin, isRecalculating }) => {
    return (
        <div className="bg-white rounded-3xl shadow-lg p-6 mb-6">
            <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                    <div className="w-12 h-12 bg-gradient-to-br from-green-400 to-emerald-500 rounded-xl flex items-center justify-center">
                        <Target size={24} className="text-white" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-gray-900">Мои цели</h2>
                        <p className="text-sm text-gray-500">Дневные показатели КБЖУ</p>
                    </div>
                </div>
            </div>

            {!profile.is_complete && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-xl text-red-600 text-sm">
                    Необходимо заполнить профиль: пол, дата рождения, рост, вес.
                </div>
            )}

            {targets ? (
                <div className="grid grid-cols-2 gap-4 mb-4">
                    <div className="bg-gradient-to-br from-orange-50 to-red-50 p-4 rounded-2xl border-2 border-orange-100">
                        <div className="text-sm text-orange-600 font-medium mb-1">Калории</div>
                        <div className="text-2xl font-bold text-orange-700">{targets.calories}</div>
                        <div className="text-xs text-orange-500 mt-1">ккал/день</div>
                    </div>
                    <div className="bg-gradient-to-br from-blue-50 to-indigo-50 p-4 rounded-2xl border-2 border-blue-100">
                        <div className="text-sm text-blue-600 font-medium mb-1">Белки</div>
                        <div className="text-2xl font-bold text-blue-700">{targets.proteins_g}</div>
                        <div className="text-xs text-blue-500 mt-1">г/день</div>
                    </div>
                    <div className="bg-gradient-to-br from-yellow-50 to-amber-50 p-4 rounded-2xl border-2 border-yellow-100">
                        <div className="text-sm text-yellow-600 font-medium mb-1">Жиры</div>
                        <div className="text-2xl font-bold text-yellow-700">{targets.fats_g}</div>
                        <div className="text-xs text-yellow-500 mt-1">г/день</div>
                    </div>
                    <div className="bg-gradient-to-br from-green-50 to-emerald-50 p-4 rounded-2xl border-2 border-green-100">
                        <div className="text-sm text-green-600 font-medium mb-1">Углеводы</div>
                        <div className="text-2xl font-bold text-green-700">{targets.carbs_g}</div>
                        <div className="text-xs text-green-500 mt-1">г/день</div>
                    </div>
                </div>
            ) : (
                <div className="text-sm text-gray-500 mb-4">Цели пока не установлены.</div>
            )}

            <button
                onClick={onRecalculateByMifflin}
                disabled={isRecalculating}
                className="w-full px-4 py-3 bg-purple-50 text-purple-600 rounded-xl hover:bg-purple-100 transition-colors font-medium disabled:opacity-60 disabled:cursor-not-allowed"
            >
                {isRecalculating ? 'Пересчёт...' : 'Рассчитать по формуле Маффина-Сан Жеора'}
            </button>
        </div>
    );
};
