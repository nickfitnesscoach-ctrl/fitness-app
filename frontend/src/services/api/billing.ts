/**
 * Billing API Module
 * 
 * Handles subscriptions, payments, and billing status.
 */

import {
    fetchWithTimeout,
    fetchWithRetry,
    getHeaders,
    log
} from './client';
import { URLS } from './urls';
import type {
    BillingMe,
    CreatePaymentRequest,
    CreatePaymentResponse,
    SubscriptionDetails,
    PaymentMethod,
    PaymentHistory,
    SubscriptionPlan
} from '../../types/billing';

// ============================================================
// Subscription Status
// ============================================================

export const getSubscriptionPlans = async (): Promise<SubscriptionPlan[]> => {
    try {
        const response = await fetchWithTimeout(URLS.plans, {
            headers: getHeaders(),
        });
        if (!response.ok) throw new Error('Failed to fetch subscription plans');
        return await response.json();
    } catch (error) {
        console.error('Error fetching subscription plans:', error);
        throw error;
    }
};

export const getBillingMe = async (): Promise<BillingMe> => {
    log('Fetching billing status');
    try {
        const response = await fetchWithRetry(URLS.billingMe, {
            headers: getHeaders(),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            log(`Billing status error: ${response.status}`);
            throw new Error(errorData.detail || errorData.error || 'Failed to fetch billing status');
        }

        const data = await response.json();
        log(`Billing status: plan=${data.plan_code}, limit=${data.daily_photo_limit}, used=${data.used_today}`);
        return data;
    } catch (error) {
        console.error('Error fetching billing status:', error);
        throw error;
    }
};

export const getSubscriptionDetails = async (): Promise<SubscriptionDetails> => {
    log('Fetching subscription details');
    try {
        const response = await fetchWithRetry(URLS.subscriptionDetails, {
            headers: getHeaders(),
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch subscription details: ${response.status}`);
        }

        const data = await response.json();
        log('Subscription details fetched successfully');
        return data;
    } catch (error) {
        log(`Failed to fetch subscription details: ${error}`);
        throw error;
    }
};

// ============================================================
// Payments
// ============================================================

export const createPayment = async (request: CreatePaymentRequest): Promise<CreatePaymentResponse> => {
    log(`Creating payment for plan: ${request.plan_code}`);
    try {
        const response = await fetchWithRetry(URLS.createPayment, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(request),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            log(`Payment creation error: ${errorData.error?.code || response.status}`);
            throw new Error(errorData.error?.message || errorData.detail || 'Failed to create payment');
        }

        const data = await response.json();
        log(`Payment created: ${data.payment_id}`);
        return data;
    } catch (error) {
        console.error('Error creating payment:', error);
        throw error;
    }
};

export const createTestLivePayment = async () => {
    log('Creating test live payment (admin only)');
    try {
        const response = await fetchWithRetry(URLS.createPayment.replace('create-payment', 'create-test-live-payment'), {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({}),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error?.message || errorData.detail || 'Не удалось создать тестовый платёж');
        }

        const data = await response.json();
        log(`Test payment created: ${data.payment_id}, mode: ${data.yookassa_mode}`);

        const isTMA = typeof window !== 'undefined' && window.Telegram?.WebApp?.initData;
        if (isTMA && window.Telegram) {
            window.Telegram.WebApp.openLink(data.confirmation_url);
        } else {
            window.location.href = data.confirmation_url;
        }

        return data;
    } catch (error) {
        console.error('Error creating test payment:', error);
        throw error;
    }
};

// ============================================================
// Subscription Management
// ============================================================

export const setAutoRenew = async (enabled: boolean): Promise<SubscriptionDetails> => {
    log(`Setting auto-renew: ${enabled}`);
    try {
        const response = await fetchWithRetry(URLS.subscriptionAutoRenew, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({ enabled }),
        });

        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error?.message || 'Failed to toggle auto-renew');
        }

        const data = await response.json();
        log('Auto-renew toggled successfully');
        return data;
    } catch (error) {
        log(`Failed to toggle auto-renew: ${error}`);
        throw error;
    }
};

// ============================================================
// Payment Methods
// ============================================================

export const getPaymentMethod = async (): Promise<PaymentMethod> => {
    log('Fetching payment method');
    try {
        const response = await fetchWithRetry(URLS.paymentMethodDetails, {
            headers: getHeaders(),
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch payment method: ${response.status}`);
        }

        const data = await response.json();
        log('Payment method fetched successfully');
        return data;
    } catch (error) {
        log(`Failed to fetch payment method: ${error}`);
        throw error;
    }
};

export const bindCard = async () => {
    log('Starting card binding flow (1₽ payment)');
    try {
        const response = await fetchWithRetry(URLS.bindCardStart, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify({}),
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            log(`Card binding error: ${errorData.error?.code || response.status}`);

            const errorMessage = errorData.error?.message || errorData.detail || 'Не удалось запустить привязку карты';
            const errorCode = errorData.detail || errorData.error?.code || 'UNKNOWN_ERROR';

            throw new Error(JSON.stringify({
                message: errorMessage,
                code: errorCode
            }));
        }

        const data = await response.json();
        log(`Card binding payment created: ${data.payment_id}`);

        const isTMA = typeof window !== 'undefined' && window.Telegram?.WebApp?.initData;
        if (isTMA && window.Telegram) {
            window.Telegram.WebApp.openLink(data.confirmation_url);
        } else {
            window.location.href = data.confirmation_url;
        }

        return data;
    } catch (error) {
        console.error('Error initiating card binding:', error);
        throw error;
    }
};

export const addPaymentMethod = async () => {
    return bindCard();
};

// ============================================================
// Payment History
// ============================================================

export const getPaymentsHistory = async (limit = 10): Promise<PaymentHistory> => {
    log(`Fetching payments history(limit: ${limit})`);
    try {
        const response = await fetchWithRetry(`${URLS.paymentsHistory}?limit=${limit}`, {
            headers: getHeaders(),
        });

        if (!response.ok) {
            throw new Error(`Failed to fetch payments history: ${response.status}`);
        }

        const data = await response.json();
        log(`Payments history fetched: ${data.results.length} items`);
        return data;
    } catch (error) {
        log(`Failed to fetch payments history: ${error}`);
        throw error;
    }
};
