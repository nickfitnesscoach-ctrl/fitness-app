import React, { useEffect, useState } from 'react';
import { Edit2, Loader2, Settings } from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import { getProfile } from '../api/profile';
import { getTargets, recalculateTargets } from '../api/nutrition';
import { NutritionTargets, Profile } from '../types/profile';
import { GoalsCard } from './profile/GoalsCard';
import { ProfileEditModal } from './profile/ProfileEditModal';
import { MifflinSurveyModal } from './profile/MifflinSurveyModal';
import { Avatar } from '../components/Avatar';

const ProfilePage: React.FC = () => {
    const { user, logout } = useAuth();
    const [profile, setProfile] = useState<Profile | null>(null);
    const [targets, setTargets] = useState<NutritionTargets | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isProfileModalOpen, setIsProfileModalOpen] = useState(false);
    const [isSurveyOpen, setIsSurveyOpen] = useState(false);
    const [isLoadingRecalc, setIsLoadingRecalc] = useState(false);

    useEffect(() => {
        const fetchData = async () => {
            setIsLoading(true);
            setError(null);
            try {
                const [profileData, targetsData] = await Promise.all([
                    getProfile(),
                    getTargets().catch(() => null),
                ]);
                setProfile(profileData);
                setTargets(targetsData);
            } catch (err) {
                console.error(err);
                setError('Не удалось загрузить профиль. Попробуйте ещё раз.');
            } finally {
                setIsLoading(false);
            }
        };

        fetchData();
    }, []);
        }

        try {
            setIsLoadingRecalc(true);
            const newTargets = await recalculateTargets('mifflin');
            setTargets(newTargets);
        } catch (err) {
            console.error(err);
            setError('Не удалось пересчитать цели. Попробуйте ещё раз.');
        } finally {
            setIsLoadingRecalc(false);
        }
    };

    const handleProfileUpdated = (updated: Profile) => {
        setProfile(updated);
    };

    const handleTargetsUpdated = (updatedTargets: NutritionTargets) => {
        setTargets(updatedTargets);
    };

    const renderContent = () => {
        if (isLoading) {
            return (
                <div className="flex justify-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
                </div>
            );
        }

        if (error) {
            return (
                <div className="bg-red-50 border border-red-200 text-red-700 rounded-2xl p-4">
                    <p className="mb-3">{error}</p>
                    <button
                        onClick={() => window.location.reload()}
                        className="px-4 py-2 bg-red-600 text-white rounded-xl"
                    >
                        Обновить страницу
                    </button>
                </div>
            );
        }

        if (!profile) return null;

        return (
            <>
                <div className="bg-white rounded-3xl shadow-xl overflow-hidden mb-6">
                    <div className="h-32 bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500"></div>
                    <div className="relative px-6 pb-6">
                        <div className="absolute -top-16 left-6">
                            <div className="w-28 h-28 bg-white rounded-full p-2 shadow-xl">
                                <Avatar
                                    className="w-full h-full rounded-full object-cover"
                                    alt={profile.name}
                                    src={undefined}
                                />
                            </div>
                        </div>
                        <div className="flex justify-end pt-4">
                            <button
                                onClick={() => setIsProfileModalOpen(true)}
                                className="flex items-center gap-2 px-4 py-2 bg-blue-50 text-blue-600 rounded-xl hover:bg-blue-100 transition-colors"
                            >
                                <Edit2 size={18} />
                                <span className="text-sm font-medium">Редактировать</span>
                            </button>
                        </div>

                        <div className="mt-4">
                            <h1 className="text-2xl font-bold text-gray-900">{profile.name}</h1>
                            <p className="text-gray-500 mt-1">@{profile.username || user?.username || 'user'}</p>
                            <p className="text-sm text-gray-400 mt-2">Telegram ID: {profile.telegram_id}</p>
                        </div>
                    </div>
                </div>

                <GoalsCard
                    profile={profile}
                    targets={targets}
                    onRecalculateByMifflin={handleRecalculateByMifflin}
                    isRecalculating={isLoadingRecalc}
                />

                <div className="bg-white rounded-3xl shadow-lg p-6 mb-6">
                    <div className="flex items-center gap-3 mb-6">
                        <div className="w-12 h-12 bg-gradient-to-br from-gray-400 to-gray-600 rounded-xl flex items-center justify-center">
                            <Settings size={24} className="text-white" />
                        </div>
                        <div>
                            <h2 className="text-xl font-bold text-gray-900">Настройки</h2>
                            <p className="text-sm text-gray-500">Управление аккаунтом</p>
                        </div>
                    </div>
                    <div className="space-y-3">
                        <div className="w-full flex items-center justify-between p-4 bg-gray-50 rounded-xl">
                            <span className="text-gray-700 font-medium">Часовой пояс</span>
                            <span className="text-sm text-gray-500">{profile.timezone || 'не указан'}</span>
                        </div>
                        <button
                            onClick={() => {
                                logout();
                                window.location.href = '/';
                            }}
                            className="w-full flex items-center justify-center gap-3 p-4 bg-red-50 text-red-600 rounded-2xl hover:bg-red-100 transition-colors font-medium shadow-sm"
                        >
                            Выйти из аккаунта
                        </button>
                    </div>
                </div>
            </>
        );
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-purple-50 p-4 pb-24">
            <div className="max-w-2xl mx-auto">
                {renderContent()}
            </div>

            <ProfileEditModal
                isOpen={isProfileModalOpen}
                profile={profile}
                onClose={() => setIsProfileModalOpen(false)}
                onProfileUpdated={handleProfileUpdated}
            />

            <MifflinSurveyModal
                isOpen={isSurveyOpen}
                profile={profile}
                onClose={() => setIsSurveyOpen(false)}
                onProfileUpdated={handleProfileUpdated}
                onTargetsUpdated={handleTargetsUpdated}
            />
        </div>
    );
};

export default ProfilePage;
