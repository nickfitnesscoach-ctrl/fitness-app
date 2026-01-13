/**
 * AppDataContext - Shared Application State
 * 
 * Provides centralized storage for app-wide data that should be loaded once:
 * - User profile
 * - Daily goals (KBJU)
 * - Subscription status (from BillingContext)
 * 
 * Features:
 * - Single API fetch on app start
 * - StrictMode double-mount protection
 * - Cache invalidation on logout
 * - Manual refresh methods for user actions
 */

import React, { createContext, useContext, useState, useRef, useCallback, useEffect } from 'react';
import { api } from '../services/api';
import { Profile } from '../types/profile';
import { useAuth } from './AuthContext';

// ============================================================
// Types
// ============================================================

interface DailyGoals {
    calories: number;
    protein: number;
    fat: number;
    carbohydrates: number;
}

interface AppDataContextType {
    // Data
    profile: Profile | null;
    goals: DailyGoals | null;

    // Loading states
    isLoading: boolean;
    isProfileLoading: boolean;
    isGoalsLoading: boolean;

    // Error states
    error: string | null;

    // Manual refresh methods (for user actions like save)
    refreshProfile: () => Promise<void>;
    refreshGoals: () => Promise<void>;

    // Cache invalidation (called on logout)
    clearCache: () => void;
}

const AppDataContext = createContext<AppDataContextType | undefined>(undefined);

// ============================================================
// Provider
// ============================================================

export const AppDataProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
    const { user } = useAuth();
    // Stable key for effects
    const userId = user?.id ?? user?.telegram_id ?? null;

    const [profile, setProfile] = useState<Profile | null>(null);
    const [goals, setGoals] = useState<DailyGoals | null>(null);
    const [isProfileLoading, setIsProfileLoading] = useState(true);
    const [isGoalsLoading, setIsGoalsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // In-flight request guards
    const profileInFlightRef = useRef<Promise<void> | null>(null);
    const goalsInFlightRef = useRef<Promise<void> | null>(null);

    /**
     * Load profile data
     */
    const loadProfile = useCallback(async () => {
        if (profileInFlightRef.current) return profileInFlightRef.current;

        const p = (async () => {
            try {
                setIsProfileLoading(true);
                const data = await api.getProfile();
                setProfile(data);
                if (error) setError(null); // Clear error on success
            } catch (err) {
                console.error('[AppDataContext] Failed to load profile:', err);
                // Don't set error - profile might not exist yet
            } finally {
                setIsProfileLoading(false);
                profileInFlightRef.current = null;
            }
        })();

        profileInFlightRef.current = p;
        return p;
    }, [error]);

    /**
     * Load daily goals
     */
    const loadGoals = useCallback(async () => {
        if (goalsInFlightRef.current) return goalsInFlightRef.current;

        const p = (async () => {
            try {
                setIsGoalsLoading(true);
                const data = await api.getDailyGoals();
                if (data && !data.error) {
                    setGoals({
                        calories: data.calories || 2000,
                        protein: data.protein || 150,
                        fat: data.fat || 70,
                        carbohydrates: data.carbohydrates || 250
                    });
                }
            } catch (err) {
                console.error('[AppDataContext] Failed to load goals:', err);
                setGoals({
                    calories: 2000,
                    protein: 150,
                    fat: 70,
                    carbohydrates: 250
                });
            } finally {
                setIsGoalsLoading(false);
                goalsInFlightRef.current = null;
            }
        })();

        goalsInFlightRef.current = p;
        return p;
    }, []);

    // Guard against multiple initializations
    const didInitRef = useRef(false);

    /**
     * Initial data load
     * Triggers when user becomes authenticated
     */
    useEffect(() => {
        if (!userId) {
            didInitRef.current = false; // Reset on logout
            setProfile(null);
            setGoals(null);
            return;
        }

        if (didInitRef.current) return;
        didInitRef.current = true;

        const loadInitialData = async () => {
            console.log('[AppDataContext] Loading initial data...');
            await Promise.all([loadProfile(), loadGoals()]);
            console.log('[AppDataContext] Initial data loaded');
        };
        void loadInitialData();
    }, [userId, loadProfile, loadGoals]);

    /**
     * Manual refresh profile (for user actions)
     */
    const refreshProfile = useCallback(async () => {
        await loadProfile();
    }, [loadProfile]);

    /**
     * Manual refresh goals (for user actions)
     */
    const refreshGoals = useCallback(async () => {
        await loadGoals();
    }, [loadGoals]);

    /**
     * Clear all cached data (called on logout)
     */
    const clearCache = useCallback(() => {
        setProfile(null);
        setGoals(null);
        console.log('[AppDataContext] Cache cleared');
    }, []);

    const isLoading = isProfileLoading || isGoalsLoading;

    return (
        <AppDataContext.Provider
            value={{
                profile,
                goals,
                isLoading,
                isProfileLoading,
                isGoalsLoading,
                error,
                refreshProfile,
                refreshGoals,
                clearCache,
            }}
        >
            {children}
        </AppDataContext.Provider>
    );
};

// ============================================================
// Hook
// ============================================================

export const useAppData = () => {
    const context = useContext(AppDataContext);
    if (!context) {
        throw new Error('useAppData must be used within AppDataProvider');
    }
    return context;
};
