import React, { useState, useEffect, useRef } from 'react';
import { User, Settings, Edit2, X, Camera, ChevronRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useAppData } from '../contexts/AppDataContext';
import { api } from '../services/api';
import { Profile } from '../types/profile';
import ProfileEditModal from '../components/ProfileEditModal';
import { calculateMifflinTargets, hasRequiredProfileData, getMissingProfileFields } from '../utils/mifflin';
import { useTelegramWebApp } from '../hooks/useTelegramWebApp';
import { useWeeklyKbjuStats } from '../hooks/useWeeklyKbjuStats';
import GoalsSection from '../components/profile/GoalsSection';
import WeeklyStatsCard from '../components/profile/WeeklyStatsCard';
import { PageContainer } from '../components/shared/PageContainer';

interface UserGoals {
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

const ProfilePage: React.FC = () => {
    const { user, isBrowserDebug } = useAuth();
    const { profile: contextProfile, goals: contextGoals, refreshProfile, refreshGoals, isLoading: contextLoading } = useAppData();
    const navigate = useNavigate();
    const { isReady, isTelegramWebApp: webAppDetected, isBrowserDebug: webAppBrowserDebug } = useTelegramWebApp();
    const [isEditing, setIsEditing] = useState(false);
    const [isEditingGoals, setIsEditingGoals] = useState(false);
    const [isWeeklyStatsOpen, setIsWeeklyStatsOpen] = useState(false);

    const [goals, setGoals] = useState<UserGoals | null>(null);
    const [editedGoals, setEditedGoals] = useState<UserGoals | null>(null);
    const [error, setError] = useState<string | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);
    const [avatarPreview, setAvatarPreview] = useState<string | null>(null);
    const [uploadingAvatar, setUploadingAvatar] = useState(false);
    const [profile, setProfile] = useState<Profile | null>(null);

    const { avgCalories, avgProtein, avgFat, avgCarbs } = useWeeklyKbjuStats();

    useEffect(() => {
        if (contextProfile) {
            setProfile(contextProfile);
            if (contextProfile.avatar_url) {
                setAvatarPreview(contextProfile.avatar_url);
            }
        }
    }, [contextProfile]);

    useEffect(() => {
        if (contextGoals) {
            setGoals(contextGoals);
        }
    }, [contextGoals]);

    const handleEditGoals = () => {
        setEditedGoals(goals || { calories: 2000, protein: 150, fat: 70, carbohydrates: 250 });
        setIsEditingGoals(true);
        setError(null);
    };

    const handleBJUChange = (field: 'protein' | 'fat' | 'carbohydrates', value: number) => {
        if (!editedGoals) return;
        const newGoals = { ...editedGoals, [field]: value };
        newGoals.calories = Math.round(newGoals.protein * 4 + newGoals.fat * 9 + newGoals.carbohydrates * 4);
        setEditedGoals(newGoals);
    };

    const handleCancelEdit = () => {
        setEditedGoals(null);
        setIsEditingGoals(false);
        setError(null);
    };

    const handleSaveGoals = async () => {
        if (!editedGoals) return;
        setError(null);
        try {
            await api.updateGoals(editedGoals);
            setGoals(editedGoals);
            setIsEditingGoals(false);
            setEditedGoals(null);
            await refreshGoals();
        } catch (err: any) {
            setError(err.message || 'Ошибка при сохранении целей');
        }
    };

    const handleAutoCalculate = () => {
        setError(null);
        if (!hasRequiredProfileData(profile)) {
            const missingFields = getMissingProfileFields(profile);
            setError(`Заполните профиль: ${missingFields.join(', ')}`);
            return;
        }
        try {
            const targets = calculateMifflinTargets(profile!);
            setEditedGoals({
                calories: targets.calories,
                protein: targets.protein,
                fat: targets.fat,
                carbohydrates: targets.carbohydrates,
            });
        } catch (err: any) {
            setError(err.message || 'Не удалось рассчитать цели');
        }
    };

    const handleProfileUpdate = (updatedProfile: Profile) => {
        setProfile(updatedProfile);
        refreshProfile();
    };

    const handleAvatarClick = () => fileInputRef.current?.click();

    const handleFileChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
        const file = event.target.files?.[0];
        if (!file) return;
        if (file.size > 5 * 1024 * 1024) {
            setError(`Файл слишком большой (> 5 МБ)`);
            return;
        }
        try {
            const objectUrl = URL.createObjectURL(file);
            setAvatarPreview(objectUrl);
        } catch (err) { }

        setUploadingAvatar(true);
        setError(null);
        try {
            const updatedProfile = await api.uploadAvatar(file);
            setProfile(updatedProfile);
            setAvatarPreview(updatedProfile.avatar_url || null);
        } catch (err: any) {
            setError(err.message || 'Не удалось загрузить фото');
            setAvatarPreview(profile?.avatar_url || null);
        } finally {
            setUploadingAvatar(false);
            if (event.target) event.target.value = '';
        }
    };

    if (!isReady) {
        return (
            <div className="min-h-screen flex items-center justify-center">
                <div className="animate-spin w-10 h-10 border-4 border-blue-600 border-t-transparent rounded-full"></div>
            </div>
        );
    }

    if (!webAppDetected && !isBrowserDebug && !webAppBrowserDebug) {
        return (
            <div className="min-h-screen flex items-center justify-center p-4">
                <div className="bg-orange-50 border-2 border-orange-200 rounded-2xl p-6 text-center max-w-md">
                    <h2 className="text-xl font-bold text-orange-900 mb-2">Откройте через Telegram</h2>
                    <p className="text-orange-700">Приложение работает только внутри Telegram.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50">
            <PageContainer className="py-6 space-y-[var(--section-gap)]">
                {/* Profile Card */}
                <div className="bg-white rounded-[var(--radius-card)] shadow-sm border border-gray-100 overflow-hidden">
                    <div className="h-28 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500"></div>
                    <div className="relative p-[var(--card-p)]">
                        <div className="absolute -top-12 left-6">
                            <div className="w-24 h-24 bg-white rounded-full p-1.5 shadow-lg cursor-pointer group relative" onClick={handleAvatarClick}>
                                <div className="w-full h-full rounded-full overflow-hidden relative">
                                    {avatarPreview ? (
                                        <img src={avatarPreview} alt="Avatar" className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="w-full h-full bg-gradient-to-br from-blue-400 to-purple-500 flex items-center justify-center">
                                            <User size={36} className="text-white" />
                                        </div>
                                    )}
                                    {uploadingAvatar && (
                                        <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                                            <div className="animate-spin w-6 h-6 border-3 border-white border-t-transparent rounded-full"></div>
                                        </div>
                                    )}
                                    {!uploadingAvatar && (
                                        <div className="absolute inset-0 bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                            <Camera size={24} className="text-white" />
                                        </div>
                                    )}
                                </div>
                                <input type="file" ref={fileInputRef} onChange={handleFileChange} accept="image/*" className="hidden" disabled={uploadingAvatar} />
                            </div>
                        </div>
                        <div className="flex justify-end pt-2">
                            <button onClick={() => setIsEditing(!isEditing)} className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 text-blue-600 rounded-xl">
                                {isEditing ? <><X size={16} /><span>Отмена</span></> : <><Edit2 size={16} /><span>Редактировать</span></>}
                            </button>
                        </div>
                        <div className="mt-4">
                            <h1 className="text-xl font-bold text-gray-900">{user?.first_name} {user?.last_name || ''}</h1>
                            <p className="text-sm text-gray-500">@{user?.username || 'user'}</p>
                            <p className="text-[10px] text-gray-400 mt-1 uppercase tracking-tighter">Telegram ID: {user?.telegram_id}</p>
                        </div>
                    </div>
                </div>

                <GoalsSection goals={goals} editedGoals={editedGoals} isEditingGoals={isEditingGoals} isLoading={contextLoading} error={error} onEdit={handleEditGoals} onChangeBju={handleBJUChange} onAutoCalculate={handleAutoCalculate} onSave={handleSaveGoals} onCancel={handleCancelEdit} />
                <WeeklyStatsCard isOpen={isWeeklyStatsOpen} onToggle={() => setIsWeeklyStatsOpen(!isWeeklyStatsOpen)} avgCalories={avgCalories} avgProtein={avgProtein} avgFat={avgFat} avgCarbs={avgCarbs} />

                <div className="bg-white rounded-[var(--radius-card)] shadow-sm border border-gray-100 p-[var(--card-p)] cursor-pointer active:scale-[0.98] transition-all" onClick={() => navigate('/settings')}>
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <div className="w-10 h-10 bg-gradient-to-br from-gray-400 to-gray-600 rounded-xl flex items-center justify-center"><Settings size={20} className="text-white" /></div>
                            <div><h2 className="text-base font-bold text-gray-900 leading-tight">Настройки</h2><p className="text-xs text-gray-500 leading-tight">Управление аккаунтом</p></div>
                        </div>
                        <ChevronRight size={20} className="text-gray-400" />
                    </div>
                </div>
            </PageContainer>
            <ProfileEditModal isOpen={isEditing} onClose={() => setIsEditing(false)} profile={profile} onProfileUpdated={handleProfileUpdate} />
        </div>
    );
};

export default ProfilePage;
