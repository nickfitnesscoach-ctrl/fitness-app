import { useState, useEffect, useCallback } from 'react';
import { api } from '../services/api';
import { Profile } from '../types/profile';
import { useAuth } from '../contexts/AuthContext';

export const useProfile = () => {
    const { user, loading: authLoading } = useAuth();
    const [profile, setProfile] = useState<Profile | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchProfile = useCallback(async () => {
        // Если авторизация еще идет или пользователя нет - не грузим профиль
        if (authLoading || !user) {
            // Если авторизация закончилась и юзера нет - значит мы не залогинены,
            // но useProfile может использоваться там, где это ок?
            // В нашем случае Dashboard требует профиль.
            // Если authLoading false и user null, то loading профиля тоже ставим false (нет данных)
            if (!authLoading && !user) {
                setLoading(false);
            }
            return;
        }

        try {
            setLoading(true);
            setError(null);
            const data = await api.getProfile();
            setProfile(data);
        } catch (err) {
            console.error('Profile fetch error:', err);
            setError(err instanceof Error ? err.message : 'Failed to load profile');
        } finally {
            setLoading(false);
        }
    }, [authLoading, user]);

    useEffect(() => {
        fetchProfile();
    }, [fetchProfile]);

    return { profile, loading: loading || authLoading, error, refetch: fetchProfile };
};
