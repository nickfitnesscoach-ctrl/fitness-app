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

import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../services/api';
import { Profile } from '../types/profile';

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
    const [profile, setProfile] = useState<Profile | null>(null);
    const [goals, setGoals] = useState<DailyGoals | null>(null);
    const [isProfileLoading, setIsProfileLoading] = useState(true);
    const [isGoalsLoading, setIsGoalsLoading] = useState(true);
    const [error] = useState<string | null>(null);

    // StrictMode protection: track if initial fetch has been done
    const hasFetchedRef = useRef(false);

    /**
     * Load profile data
     */
    const loadProfile = useCallback(async () => {
        try {
            setIsProfileLoading(true);
            const data = await api.getProfile();
            setProfile(data);
        } catch (err) {
            console.error('[AppDataContext] Failed to load profile:', err);
            // Don't set error - profile might not exist yet
        } finally {
            setIsProfileLoading(false);
        }
    }, []);

    /**
     * Load daily goals
     */
    const loadGoals = useCallback(async () => {
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
            // Use defaults if load fails
            setGoals({
                calories: 2000,
                protein: 150,
                fat: 70,
                carbohydrates: 250
            });
        } finally {
            setIsGoalsLoading(false);
        }
    }, []);

    /**
     * Initial data load - runs once on mount
     * Protected against StrictMode double-mount
     */
    useEffect(() => {
        // StrictMode protection: only fetch once
        if (hasFetchedRef.current) {
            return;
        }
        hasFetchedRef.current = true;

        const loadInitialData = async () => {
            console.log('[AppDataContext] Loading initial data...');
            await Promise.all([loadProfile(), loadGoals()]);
            console.log('[AppDataContext] Initial data loaded');
        };

        loadInitialData();
    }, [loadProfile, loadGoals]);

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
        hasFetchedRef.current = false; // Allow re-fetch after re-login
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
