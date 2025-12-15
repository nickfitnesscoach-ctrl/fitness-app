/**
 * API URL Configuration
 */

import { API_BASE } from './client';
import { TRAINER_PANEL_AUTH_URL as TRAINER_AUTH_URL } from '../../config/env';

const TRAINER_PANEL_AUTH_URL = TRAINER_AUTH_URL;

export const URLS = {
    // Telegram endpoints
    auth: `${API_BASE}/telegram/auth/`,
    trainerPanelAuth: TRAINER_PANEL_AUTH_URL,
    applications: `${API_BASE}/telegram/applications/`,
    clients: `${API_BASE}/telegram/clients/`,
    inviteLink: `${API_BASE}/telegram/invite-link/`,
    subscribers: `${API_BASE}/telegram/subscribers/`,
    
    // Nutrition endpoints
    meals: `${API_BASE}/meals/`,
    goals: `${API_BASE}/goals/`,
    calculateGoals: `${API_BASE}/goals/calculate/`,
    setAutoGoals: `${API_BASE}/goals/set-auto/`,
    weeklyStats: `${API_BASE}/stats/weekly/`,
    
    // User endpoints
    profile: `${API_BASE}/users/profile/`,
    uploadAvatar: `${API_BASE}/users/profile/avatar/`,
    
    // Billing endpoints (current - use these)
    billingMe: `${API_BASE}/billing/me/`,
    subscriptionDetails: `${API_BASE}/billing/subscription/`,
    subscriptionAutoRenew: `${API_BASE}/billing/subscription/autorenew/`,
    createPayment: `${API_BASE}/billing/create-payment/`,
    paymentMethodDetails: `${API_BASE}/billing/payment-method/`,
    paymentsHistory: `${API_BASE}/billing/payments/`,
    bindCardStart: `${API_BASE}/billing/bind-card/start/`,
    plans: `${API_BASE}/billing/plans/`,
    
    // Legacy billing endpoints (deprecated - will be removed in v2.0)
    plan: `${API_BASE}/billing/plan`,  // Use billingMe instead
    cancelSubscription: `${API_BASE}/billing/cancel/`,  // Not used
    resumeSubscription: `${API_BASE}/billing/resume/`,  // Not used
    paymentMethods: `${API_BASE}/billing/payment-methods/`,  // Use paymentMethodDetails
    
    // AI endpoints
    recognize: `${API_BASE}/ai/recognize/`,
    taskStatus: (taskId: string) => `${API_BASE}/ai/task/${taskId}/`,
};
