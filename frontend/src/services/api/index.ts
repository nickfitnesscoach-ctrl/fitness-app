/**
 * API Module - Main Export
 * 
 * Re-exports all API functions and provides backward-compatible `api` object.
 */

// Re-export everything from modules
export * from './client';
export * from './types';
export * from './urls';

// Import modules for backward-compatible api object
import * as auth from './auth';
import * as nutrition from './nutrition';
import * as billing from './billing';
import * as profile from './profile';
import * as trainer from './trainer';
import { getLogs, getDebugInfo, resolveImageUrl } from './client';

// AI module available via direct import: import { ... } from '@/features/ai'

// Re-export individual modules for direct imports
export { auth, nutrition, billing, profile, trainer };

/**
 * Backward-compatible API object
 * 
 * Usage:
 *   import { api } from '../services/api';
 *   await api.getMeals('2025-12-06');
 * 
 * New usage (preferred):
 *   import { nutrition } from '../services/api';
 *   await nutrition.getMeals('2025-12-06');
 */
export const api = {
    // Debug
    getLogs,
    getDebugInfo,

    // Utility
    resolveImageUrl,

    // Legacy JWT methods (no-op for WebApp)
    setAccessToken: (_token: string) => {
        console.log('[API] setAccessToken called (ignored - WebApp uses Header auth)');
    },
    getAccessToken: () => null,
    clearToken: () => { },

    // Auth (authentication only)
    authenticate: auth.authenticate,
    trainerPanelAuth: auth.trainerPanelAuth,

    // Trainer Panel (SSOT: services/api/trainer.ts)
    // @see features/trainer-panel/docs/TRAINER_API.md
    getApplications: trainer.getApplications,
    deleteApplication: trainer.deleteApplication,
    updateApplicationStatus: trainer.updateApplicationStatus,
    getClients: trainer.getClients,
    addClient: trainer.addClient,
    removeClient: trainer.removeClient,
    getInviteLink: trainer.getInviteLink,
    getSubscribers: trainer.getSubscribers,

    // Nutrition
    getMeals: nutrition.getMeals,
    createMeal: nutrition.createMeal,
    deleteMeal: nutrition.deleteMeal,
    getMealAnalysis: nutrition.getMealAnalysis,
    addFoodItem: nutrition.addFoodItem,
    deleteFoodItem: nutrition.deleteFoodItem,
    updateFoodItem: nutrition.updateFoodItem,
    getDailyGoals: nutrition.getDailyGoals,
    updateGoals: nutrition.updateGoals,
    calculateGoals: nutrition.calculateGoals,
    setAutoGoals: nutrition.setAutoGoals,
    getWeeklyStats: nutrition.getWeeklyStats,

    // AI: Import directly from '@/features/ai' (no legacy re-export needed)

    // Billing
    getSubscriptionPlans: billing.getSubscriptionPlans,
    getBillingMe: billing.getBillingMe,
    getSubscriptionDetails: billing.getSubscriptionDetails,
    createPayment: billing.createPayment,
    createTestLivePayment: billing.createTestLivePayment,
    setAutoRenew: billing.setAutoRenew,
    getPaymentMethod: billing.getPaymentMethod,
    bindCard: billing.bindCard,
    addPaymentMethod: billing.addPaymentMethod,
    getPaymentsHistory: billing.getPaymentsHistory,

    // Profile
    getProfile: profile.getProfile,
    updateProfile: profile.updateProfile,
    uploadAvatar: profile.uploadAvatar,
};

// Default export for backward compatibility
export default api;
