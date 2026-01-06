import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../../../services/api';
import { useBilling } from '../../../contexts/BillingContext';

interface UsePaymentPollingOptions {
    intervalMs?: number;   // default 3000
    timeoutMs?: number;    // default 90000
    targetPlanCode?: string;
    flagTtlMs?: number;    // default 10 minutes
}

interface UsePaymentPollingResult {
    isPolling: boolean;
    startPolling: (params?: { targetPlanCode?: string }) => void;
    stopPolling: () => void;
    isTimedOut: boolean;
    pollCount: number;
}

const LS_KEY = 'billing_payment_poll_v2';

type PollFlag = {
    ts: number;
    targetPlanCode?: string;
};

function readFlag(): PollFlag | null {
    try {
        const raw = localStorage.getItem(LS_KEY);
        if (!raw) return null;
        const data = JSON.parse(raw);
        if (!data || typeof data.ts !== 'number') return null;
        return data as PollFlag;
    } catch {
        return null;
    }
}

function writeFlag(flag: PollFlag): void {
    localStorage.setItem(LS_KEY, JSON.stringify(flag));
}

export function setPollingFlagForPayment(params?: { targetPlanCode?: string }) {
    writeFlag({ ts: Date.now(), targetPlanCode: params?.targetPlanCode });
}

export function clearPollingFlag() {
    localStorage.removeItem(LS_KEY);
}

export const usePaymentPolling = (options: UsePaymentPollingOptions = {}): UsePaymentPollingResult => {
    const {
        intervalMs = 3000,
        timeoutMs = 90000,
        targetPlanCode,
        flagTtlMs = 10 * 60 * 1000,
    } = options;

    const billing = useBilling();

    const [isPolling, setIsPolling] = useState(false);
    const [isTimedOut, setIsTimedOut] = useState(false);
    const [pollCount, setPollCount] = useState(0);

    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const mountedRef = useRef(true);
    const activeTargetRef = useRef<string | undefined>(targetPlanCode);

    const stopPolling = useCallback(() => {
        if (intervalRef.current) clearInterval(intervalRef.current);
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        intervalRef.current = null;
        timeoutRef.current = null;
        setIsPolling(false);
    }, []);

    const pollOnce = useCallback(async () => {
        if (!mountedRef.current) return;

        try {
            const me = await api.getBillingMe();
            setPollCount((p) => p + 1);

            const t = activeTargetRef.current;
            const isSuccess = t ? me.plan_code === t : me.plan_code !== 'FREE';

            if (isSuccess) {
                clearPollingFlag();
                stopPolling();
                await billing.refresh();
            }
        } catch (err) {
            // errors are ok; keep polling
            console.warn('[billing] polling error:', err);
        }
    }, [billing, stopPolling]);

    const startPolling = useCallback(
        (params?: { targetPlanCode?: string }) => {
            activeTargetRef.current = params?.targetPlanCode ?? targetPlanCode;

            setIsPolling(true);
            setIsTimedOut(false);
            setPollCount(0);

            if (intervalRef.current) clearInterval(intervalRef.current);
            if (timeoutRef.current) clearTimeout(timeoutRef.current);

            intervalRef.current = setInterval(pollOnce, intervalMs);
            timeoutRef.current = setTimeout(() => {
                if (!mountedRef.current) return;
                stopPolling();
                clearPollingFlag();
                setIsTimedOut(true);
            }, timeoutMs);

            // immediate first poll
            pollOnce();
        },
        [intervalMs, timeoutMs, pollOnce, stopPolling, targetPlanCode],
    );

    useEffect(() => {
        mountedRef.current = true;
        return () => {
            mountedRef.current = false;
            if (intervalRef.current) clearInterval(intervalRef.current);
            if (timeoutRef.current) clearTimeout(timeoutRef.current);
        };
    }, []);

    // Resume polling after return from payment (flag set BEFORE redirect)
    useEffect(() => {
        const flag = readFlag();
        if (!flag) return;

        const age = Date.now() - flag.ts;
        if (age < 0 || age > flagTtlMs) {
            clearPollingFlag();
            return;
        }

        // Resume only once
        clearPollingFlag();
        startPolling({ targetPlanCode: flag.targetPlanCode });
    }, [flagTtlMs, startPolling]);

    return {
        isPolling,
        startPolling,
        stopPolling,
        isTimedOut,
        pollCount,
    };
};
