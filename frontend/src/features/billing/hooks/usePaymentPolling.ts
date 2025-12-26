import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../../../services/api';
import { useBilling } from '../../../contexts/BillingContext';

interface UsePaymentPollingOptions {
    /** Polling interval in milliseconds (default: 3000) */
    intervalMs?: number;
    /** Maximum polling duration in milliseconds (default: 90000 = 90s) */
    timeoutMs?: number;
    /** Target plan code to detect (if not provided, any non-FREE is considered success) */
    targetPlanCode?: string;
}

interface UsePaymentPollingResult {
    /** Whether polling is currently active */
    isPolling: boolean;
    /** Start polling for subscription update */
    startPolling: () => void;
    /** Stop polling manually */
    stopPolling: () => void;
    /** Whether timeout was reached without success */
    isTimedOut: boolean;
    /** Number of poll attempts made */
    pollCount: number;
}

/**
 * Hook for polling subscription status after payment.
 *
 * After a user completes payment and returns to the app, this hook
 * polls /billing/me/ to detect when the subscription has been activated.
 *
 * Usage:
 * ```tsx
 * const { isPolling, startPolling, isTimedOut } = usePaymentPolling();
 *
 * const handlePayment = async () => {
 *   const { confirmation_url } = await api.createPayment(...);
 *   startPolling(); // Start polling before redirect
 *   window.location.href = confirmation_url;
 * };
 *
 * // After return from payment:
 * if (isTimedOut) {
 *   return <Button onClick={() => billing.refresh()}>Обновить статус</Button>;
 * }
 * ```
 */
export const usePaymentPolling = (options: UsePaymentPollingOptions = {}): UsePaymentPollingResult => {
    const {
        intervalMs = 3000,
        timeoutMs = 90000,
        targetPlanCode,
    } = options;

    const billing = useBilling();
    const [isPolling, setIsPolling] = useState(false);
    const [isTimedOut, setIsTimedOut] = useState(false);
    const [pollCount, setPollCount] = useState(0);

    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const startTimeRef = useRef<number | null>(null);
    const mountedRef = useRef(true);

    const stopPolling = useCallback(() => {
        if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
        }
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
            timeoutRef.current = null;
        }
        setIsPolling(false);
        startTimeRef.current = null;
    }, []);

    const pollOnce = useCallback(async () => {
        if (!mountedRef.current) return;

        try {
            const me = await api.getBillingMe();
            setPollCount(prev => prev + 1);

            if (!mountedRef.current) return;

            const isSuccess = targetPlanCode
                ? me.plan_code === targetPlanCode
                : me.plan_code !== 'FREE';

            if (isSuccess) {
                console.log('[usePaymentPolling] Subscription activated:', me.plan_code);
                stopPolling();
                // Refresh full billing context
                await billing.refresh();
            }
        } catch (error) {
            console.warn('[usePaymentPolling] Poll error:', error);
            // Continue polling on error
        }
    }, [targetPlanCode, stopPolling, billing]);

    const startPolling = useCallback(() => {
        // Reset state
        setIsPolling(true);
        setIsTimedOut(false);
        setPollCount(0);
        startTimeRef.current = Date.now();

        // Clear any existing timers
        if (intervalRef.current) clearInterval(intervalRef.current);
        if (timeoutRef.current) clearTimeout(timeoutRef.current);

        // Start interval
        intervalRef.current = setInterval(pollOnce, intervalMs);

        // Set timeout
        timeoutRef.current = setTimeout(() => {
            if (mountedRef.current) {
                console.log('[usePaymentPolling] Timeout reached');
                stopPolling();
                setIsTimedOut(true);
            }
        }, timeoutMs);

        // Poll immediately on start
        pollOnce();
    }, [intervalMs, timeoutMs, pollOnce, stopPolling]);

    // Cleanup on unmount
    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
            if (intervalRef.current) clearInterval(intervalRef.current);
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
        };
    }, []);

    // Also check if we should poll on mount (in case user returned from payment)
    // This is triggered by a localStorage flag set before payment redirect
    useEffect(() => {
        const shouldPoll = localStorage.getItem('billing_poll_active');
        if (shouldPoll === 'true') {
            console.log('[usePaymentPolling] Resuming polling after return');
            localStorage.removeItem('billing_poll_active');
            startPolling();
        }
    }, [startPolling]);

    return {
        isPolling,
        startPolling,
        stopPolling,
        isTimedOut,
        pollCount,
    };
};

/**
 * Set flag before redirecting to payment to trigger polling on return.
 *
 * Usage:
 * ```ts
 * setPollingFlagForPayment();
 * window.Telegram.WebApp.openLink(confirmation_url);
 * ```
 */
export const setPollingFlagForPayment = () => {
    localStorage.setItem('billing_poll_active', 'true');
};

/**
 * Clear polling flag (e.g., on payment cancel).
 */
export const clearPollingFlag = () => {
    localStorage.removeItem('billing_poll_active');
};
