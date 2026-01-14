import React, { useState, useEffect } from 'react';
import { X, Save, Activity, Calendar, Ruler, Weight, Target, User } from 'lucide-react';
import { api } from '../services/api';
import { Profile } from '../types/profile';
import { useAppData } from '../contexts/AppDataContext';

export type { Profile };

interface ProfileEditModalProps {
    isOpen: boolean;
    onClose: () => void;
    profile: Profile | null;
    onProfileUpdated: (updatedProfile: Profile) => void;
}

const ProfileEditModal: React.FC<ProfileEditModalProps> = ({ isOpen, onClose, profile, onProfileUpdated }) => {
    const { setProfile } = useAppData();
    const [formData, setFormData] = useState<Partial<Profile>>({});
    const [isSaving, setIsSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (isOpen && profile) {
            setFormData({
                gender: profile.gender || 'M',
                birth_date: profile.birth_date || '',
                height: profile.height || undefined,
                weight: profile.weight || undefined,
                activity_level: profile.activity_level || 'sedentary',
                goal_type: profile.goal_type || 'maintenance',
                timezone: profile.timezone || undefined,
            });
            setError(null);
        }
    }, [profile, isOpen]);

    if (!isOpen) return null;

    const handleChange = (field: keyof Profile, value: any) => {
        setFormData(prev => ({ ...prev, [field]: value }));
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setIsSaving(true);
        setError(null);

        try {
            // Prepare payload with only non-empty fields
            const payload: Partial<Profile> = {};

            // Only add fields that have valid values
            if (formData.gender) {
                payload.gender = formData.gender;
            }
            if (formData.birth_date) {
                payload.birth_date = formData.birth_date;
            }
            if (formData.activity_level) {
                payload.activity_level = formData.activity_level;
            }
            if (formData.goal_type) {
                payload.goal_type = formData.goal_type;
            }

            // Validate numeric fields before sending
            if (formData.height) {
                const height = Number(formData.height);
                if (isNaN(height) || height < 50 || height > 250) {
                    setError('Рост должен быть от 50 до 250 см');
                    setIsSaving(false);
                    return;
                }
                payload.height = height;
            }

            if (formData.weight) {
                const weight = Number(formData.weight);
                if (isNaN(weight) || weight < 20 || weight > 500) {
                    setError('Вес должен быть от 20 до 500 кг');
                    setIsSaving(false);
                    return;
                }
                payload.weight = weight;
            }

            if (formData.timezone) {
                payload.timezone = formData.timezone;
            }

            console.log('[ProfileEditModal] Updating profile with payload:', payload);
            const saved = await api.updateProfile(payload);
            console.log('[ProfileEditModal] Profile updated successfully:', saved);
            // SSOT: Update context directly with server response
            setProfile(saved);
            onProfileUpdated(saved);
            onClose();
        } catch (err: any) {
            console.error('[ProfileEditModal] Failed to update profile:', err);

            // Parse detailed error messages from backend
            let errorMessage = 'Ошибка при сохранении профиля';

            if (err.message) {
                errorMessage = err.message;
            }

            // Handle field-level validation errors
            if (err.response?.data) {
                const errorData = err.response.data;

                // Check for field-specific errors
                if (typeof errorData === 'object' && !errorData.detail && !errorData.error) {
                    const fieldErrors = Object.entries(errorData)
                        .map(([field, messages]) => {
                            const fieldName = field === 'birth_date' ? 'Дата рождения' :
                                field === 'height' ? 'Рост' :
                                    field === 'weight' ? 'Вес' :
                                        field === 'gender' ? 'Пол' :
                                            field;
                            return `${fieldName}: ${Array.isArray(messages) ? messages.join(', ') : messages}`;
                        })
                        .join('\n');

                    if (fieldErrors) {
                        errorMessage = fieldErrors;
                    }
                } else if (errorData.detail) {
                    errorMessage = errorData.detail;
                } else if (errorData.error) {
                    errorMessage = errorData.error;
                }
            }

            setError(errorMessage);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <div className="fixed inset-0 z-[60] flex items-end sm:items-center justify-center sm:p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white w-full sm:w-[480px] h-[98vh] sm:h-auto sm:max-h-[95vh] rounded-t-3xl sm:rounded-3xl shadow-2xl flex flex-col animate-in slide-in-from-bottom duration-300">
                {/* Header - Fixed */}
                <div className="flex-none px-6 py-4 border-b border-gray-100 flex justify-between items-center bg-white rounded-t-3xl">
                    <h2 className="text-xl font-bold text-gray-900">Редактировать профиль</h2>
                    <button
                        onClick={onClose}
                        className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-500"
                    >
                        <X size={24} />
                    </button>
                </div>

                {/* Form - Main Container */}
                <form onSubmit={handleSubmit} className="flex flex-col flex-1 min-h-0">
                    {/* Scrollable Content */}
                    <div className="flex-1 overflow-y-auto p-6 space-y-6">
                        {error && (
                            <div className="p-4 bg-red-50 text-red-600 rounded-xl text-sm">
                                {error}
                            </div>
                        )}

                        {/* Gender */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
                                <User size={18} className="text-blue-500" />
                                Пол
                            </label>
                            <div className="grid grid-cols-2 gap-3">
                                <button
                                    type="button"
                                    onClick={() => handleChange('gender', 'M')}
                                    className={`p-3 rounded-xl border-2 transition-all font-medium ${formData.gender === 'M'
                                        ? 'border-blue-500 bg-blue-50 text-blue-700'
                                        : 'border-gray-200 hover:border-blue-200 text-gray-600'
                                        }`}
                                >
                                    Мужской
                                </button>
                                <button
                                    type="button"
                                    onClick={() => handleChange('gender', 'F')}
                                    className={`p-3 rounded-xl border-2 transition-all font-medium ${formData.gender === 'F'
                                        ? 'border-pink-500 bg-pink-50 text-pink-700'
                                        : 'border-gray-200 hover:border-pink-200 text-gray-600'
                                        }`}
                                >
                                    Женский
                                </button>
                            </div>
                        </div>

                        {/* Date of Birth */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
                                <Calendar size={18} className="text-purple-500" />
                                Дата рождения
                            </label>
                            <input
                                type="date"
                                value={formData.birth_date}
                                onChange={(e) => handleChange('birth_date', e.target.value)}
                                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
                            />
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            {/* Height */}
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
                                    <Ruler size={18} className="text-indigo-500" />
                                    Рост (см)
                                </label>
                                <input
                                    type="number"
                                    value={formData.height}
                                    onChange={(e) => handleChange('height', e.target.value)}
                                    className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                                    placeholder="175"
                                />
                            </div>

                            {/* Weight */}
                            <div className="space-y-2">
                                <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
                                    <Weight size={18} className="text-orange-500" />
                                    Вес (кг)
                                </label>
                                <input
                                    type="number"
                                    value={formData.weight}
                                    onChange={(e) => handleChange('weight', e.target.value)}
                                    className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent transition-all"
                                    placeholder="70"
                                />
                            </div>
                        </div>

                        {/* Activity Level */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
                                <Activity size={18} className="text-green-500" />
                                Уровень активности
                            </label>
                            <select
                                value={formData.activity_level}
                                onChange={(e) => handleChange('activity_level', e.target.value)}
                                className="w-full p-3 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-green-500 focus:border-transparent transition-all appearance-none"
                            >
                                <option value="sedentary">Сидячий образ жизни</option>
                                <option value="lightly_active">Легкая активность (1-3 раза/нед)</option>
                                <option value="moderately_active">Средняя активность (3-5 раз/нед)</option>
                                <option value="very_active">Высокая активность (6-7 раз/нед)</option>
                                <option value="extra_active">Экстремальная активность</option>
                            </select>
                        </div>

                        {/* Goal */}
                        <div className="space-y-2">
                            <label className="text-sm font-medium text-gray-700 flex items-center gap-2">
                                <Target size={18} className="text-red-500" />
                                Цель
                            </label>
                            <div className="grid grid-cols-1 gap-2">
                                {[
                                    { value: 'weight_loss', label: 'Похудение', color: 'text-green-600 bg-green-50 border-green-200' },
                                    { value: 'maintenance', label: 'Поддержание формы', color: 'text-blue-600 bg-blue-50 border-blue-200' },
                                    { value: 'weight_gain', label: 'Набор массы', color: 'text-orange-600 bg-orange-50 border-orange-200' }
                                ].map((option) => (
                                    <button
                                        key={option.value}
                                        type="button"
                                        onClick={() => handleChange('goal_type', option.value)}
                                        className={`p-3 rounded-xl border-2 text-left transition-all ${formData.goal_type === option.value
                                            ? `${option.color} border-current`
                                            : 'border-gray-100 hover:bg-gray-50 text-gray-600'
                                            }`}
                                    >
                                        <span className="font-medium">{option.label}</span>
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>

                    {/* Footer - Fixed */}
                    <div className="flex-none p-4 border-t border-gray-100 bg-white safe-area-bottom rounded-b-3xl">
                        <button
                            type="submit"
                            disabled={isSaving}
                            className="w-full py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-2xl font-bold text-lg shadow-lg hover:shadow-xl transition-all disabled:opacity-70 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                            {isSaving ? (
                                <>
                                    <div className="w-6 h-6 border-2 border-white border-t-transparent rounded-full animate-spin" />
                                    <span>Сохраняю...</span>
                                </>
                            ) : (
                                <>
                                    <Save size={20} />
                                    Сохранить изменения
                                </>
                            )}
                        </button>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default ProfileEditModal;
