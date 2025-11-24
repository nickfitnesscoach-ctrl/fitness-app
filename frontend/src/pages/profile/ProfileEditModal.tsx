import React, { useEffect, useState } from 'react';
import { X } from 'lucide-react';
import { ActivityLevel, GoalType, Profile, Sex } from '../../types/profile';
import { updateProfile } from '../../api/profile';

interface ProfileEditModalProps {
    isOpen: boolean;
    profile: Profile | null;
    onClose: () => void;
    onProfileUpdated: (profile: Profile) => void;
}

interface ProfileFormValues {
    sex?: Sex;
    birthdate?: string;
    height_cm?: number;
    weight_kg?: number;
    activity_level?: ActivityLevel;
    goal?: GoalType;
    timezone?: string;
}

const activityOptions: { value: ActivityLevel; label: string }[] = [
    { value: 'low', label: 'Низкая' },
    { value: 'moderate', label: 'Умеренная' },
    { value: 'high', label: 'Высокая' },
    { value: 'athlete', label: 'Атлет' },
];

const goalOptions: { value: GoalType; label: string }[] = [
    { value: 'loss', label: 'Похудение' },
    { value: 'maintenance', label: 'Поддержание' },
    { value: 'gain', label: 'Набор массы' },
];

export const ProfileEditModal: React.FC<ProfileEditModalProps> = ({ isOpen, profile, onClose, onProfileUpdated }) => {
    const [formValues, setFormValues] = useState<ProfileFormValues>({});
    const [errors, setErrors] = useState<Partial<Record<keyof ProfileFormValues, string>>>({});
    const [isSubmitting, setIsSubmitting] = useState(false);

    useEffect(() => {
        if (profile) {
            setFormValues({
                sex: profile.sex,
                birthdate: profile.birthdate,
                height_cm: profile.height_cm,
                weight_kg: profile.weight_kg,
                activity_level: profile.activity_level,
                goal: profile.goal,
                timezone: profile.timezone,
            });
        }
    }, [profile]);

    if (!isOpen) return null;

    const validate = (values: ProfileFormValues) => {
        const nextErrors: Partial<Record<keyof ProfileFormValues, string>> = {};
        if (!values.sex) {
            nextErrors.sex = 'Укажите пол';
        }
        if (!values.birthdate) {
            nextErrors.birthdate = 'Укажите дату рождения';
        } else {
            const birthDate = new Date(values.birthdate);
            const now = new Date();
            const minDate = new Date();
            minDate.setFullYear(minDate.getFullYear() - 14);
            if (birthDate > now) {
                nextErrors.birthdate = 'Дата рождения не может быть в будущем';
            } else if (birthDate > minDate) {
                nextErrors.birthdate = 'Возраст должен быть старше 14 лет';
            }
        }
        if (!values.height_cm || values.height_cm < 120 || values.height_cm > 250) {
            nextErrors.height_cm = 'Рост должен быть от 120 до 250 см';
        }
        if (!values.weight_kg || values.weight_kg < 30 || values.weight_kg > 300) {
            nextErrors.weight_kg = 'Вес должен быть от 30 до 300 кг';
        }
        if (!values.activity_level) {
            nextErrors.activity_level = 'Выберите активность';
        }
        return nextErrors;
    };

    const handleChange = (field: keyof ProfileFormValues, value: string | number | undefined) => {
        setFormValues(prev => ({ ...prev, [field]: value }));
    };

    const handleSubmit = async () => {
        const validationErrors = validate(formValues);
        setErrors(validationErrors);
        if (Object.keys(validationErrors).length > 0) return;

        try {
            setIsSubmitting(true);
            const updated = await updateProfile(formValues);
            onProfileUpdated(updated);
            onClose();
        } catch (error) {
            console.error(error);
            alert('Не удалось сохранить профиль. Попробуйте ещё раз.');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-end sm:items-center justify-center z-50">
            <div className="bg-white rounded-t-3xl sm:rounded-3xl w-full sm:max-w-lg p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
                <div className="flex items-center justify-between mb-4">
                    <h3 className="text-lg font-bold text-gray-900">Редактировать профиль</h3>
                    <button onClick={onClose} className="p-2 rounded-full hover:bg-gray-100">
                        <X size={20} />
                    </button>
                </div>

                <div className="space-y-4">
                    <div>
                        <label className="text-sm font-medium text-gray-700">Пол</label>
                        <div className="flex gap-3 mt-2">
                            {(['male', 'female'] as Sex[]).map(option => (
                                <button
                                    key={option}
                                    onClick={() => handleChange('sex', option)}
                                    className={`flex-1 py-3 rounded-2xl border text-center ${
                                        formValues.sex === option
                                            ? 'border-blue-500 bg-blue-50 text-blue-600'
                                            : 'border-gray-200 text-gray-700'
                                    }`}
                                >
                                    {option === 'male' ? 'Мужской' : 'Женский'}
                                </button>
                            ))}
                        </div>
                        {errors.sex && <p className="text-xs text-red-500 mt-1">{errors.sex}</p>}
                    </div>

                    <div>
                        <label className="text-sm font-medium text-gray-700">Дата рождения</label>
                        <input
                            type="date"
                            value={formValues.birthdate || ''}
                            onChange={e => handleChange('birthdate', e.target.value)}
                            className="w-full mt-2 px-3 py-3 border rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                        {errors.birthdate && <p className="text-xs text-red-500 mt-1">{errors.birthdate}</p>}
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                        <div>
                            <label className="text-sm font-medium text-gray-700">Рост (см)</label>
                            <input
                                type="number"
                                value={formValues.height_cm || ''}
                                onChange={e => handleChange('height_cm', Number(e.target.value))}
                                className="w-full mt-2 px-3 py-3 border rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            {errors.height_cm && <p className="text-xs text-red-500 mt-1">{errors.height_cm}</p>}
                        </div>
                        <div>
                            <label className="text-sm font-medium text-gray-700">Вес (кг)</label>
                            <input
                                type="number"
                                value={formValues.weight_kg || ''}
                                onChange={e => handleChange('weight_kg', Number(e.target.value))}
                                className="w-full mt-2 px-3 py-3 border rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                            />
                            {errors.weight_kg && <p className="text-xs text-red-500 mt-1">{errors.weight_kg}</p>}
                        </div>
                    </div>

                    <div>
                        <label className="text-sm font-medium text-gray-700">Уровень активности</label>
                        <select
                            value={formValues.activity_level || ''}
                            onChange={e => handleChange('activity_level', e.target.value as ActivityLevel)}
                            className="w-full mt-2 px-3 py-3 border rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                            <option value="">Выберите активность</option>
                            {activityOptions.map(option => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                        {errors.activity_level && <p className="text-xs text-red-500 mt-1">{errors.activity_level}</p>}
                    </div>

                    <div>
                        <label className="text-sm font-medium text-gray-700">Цель</label>
                        <select
                            value={formValues.goal || ''}
                            onChange={e => handleChange('goal', e.target.value as GoalType)}
                            className="w-full mt-2 px-3 py-3 border rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                        >
                            <option value="">Выберите цель</option>
                            {goalOptions.map(option => (
                                <option key={option.value} value={option.value}>
                                    {option.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label className="text-sm font-medium text-gray-700">Часовой пояс</label>
                        <input
                            type="text"
                            placeholder="Europe/Moscow"
                            value={formValues.timezone || ''}
                            onChange={e => handleChange('timezone', e.target.value)}
                            className="w-full mt-2 px-3 py-3 border rounded-2xl focus:outline-none focus:ring-2 focus:ring-blue-500"
                        />
                    </div>
                </div>

                <div className="flex gap-3 mt-6">
                    <button
                        onClick={handleSubmit}
                        disabled={isSubmitting}
                        className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-medium disabled:opacity-60"
                    >
                        {isSubmitting ? 'Сохранение...' : 'Сохранить'}
                    </button>
                    <button
                        onClick={onClose}
                        className="flex-1 px-4 py-3 bg-gray-100 text-gray-700 rounded-xl hover:bg-gray-200 transition-colors font-medium"
                    >
                        Отменить
                    </button>
                </div>
            </div>
        </div>
    );
};
