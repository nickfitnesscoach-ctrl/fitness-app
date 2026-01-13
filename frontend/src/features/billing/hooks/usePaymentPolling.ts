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

/**
 * Читаем “флажок” из localStorage, чтобы продолжить проверку оплаты после возвращения с платежной страницы.
 * Если localStorage недоступен — просто не резюмим (это ок).
 */
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
    try {
        localStorage.setItem(LS_KEY, JSON.stringify(flag));
    } catch {
        // localStorage может быть недоступен (private mode / ограничения браузера)
        // в этом случае просто не сохраняем флаг — поллинг всё равно можно запустить вручную
    }
}

export function setPollingFlagForPayment(params?: { targetPlanCode?: string }) {
    writeFlag({ ts: Date.now(), targetPlanCode: params?.targetPlanCode });
}

export function clearPollingFlag() {
    try {
        localStorage.removeItem(LS_KEY);
    } catch {
        // ignore
    }
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

    // “Жив ли компонент?” — чтобы не обновлять state после ухода со страницы
    const mountedRef = useRef(false);

    // Текущая цель поллинга (какой план ждём). Берём её прямо перед стартом.
    const activeTargetRef = useRef<string | undefined>(targetPlanCode);

    // Токен-версия запуска: защищает от гонок, когда старый pollOnce завершился после stop/start
    const runIdRef = useRef(0);

    const clearTimers = useCallback(() => {
        if (intervalRef.current) clearInterval(intervalRef.current);
        if (timeoutRef.current) clearTimeout(timeoutRef.current);
        intervalRef.current = null;
        timeoutRef.current = null;
    }, []);

    const stopPolling = useCallback(() => {
        // “Остановить” = выключить таймеры и сказать UI, что мы не поллим
        clearTimers();
        setIsPolling(false);
    }, [clearTimers]);

    const pollOnce = useCallback(async () => {
        if (!mountedRef.current) return;

        // Снимок текущего runId: если во время await случится stop/start,
        // этот pollOnce не должен ничего менять.
        const myRunId = runIdRef.current;

        try {
            const me = await api.getBillingMe();

            if (!mountedRef.current) return;
            if (runIdRef.current !== myRunId) return;

            setPollCount((p) => p + 1);

            const t = activeTargetRef.current;
            const isSuccess = t ? me.plan_code === t : me.plan_code !== 'FREE';

            if (isSuccess) {
                // Мы “дождались” обновления подписки → чистим флаг, останавливаем поллинг и обновляем контекст
                clearPollingFlag();
                stopPolling();
                await billing.refresh();
            }
        } catch (err) {
            // Ошибки сети/сервака допустимы: продолжаем пытаться до таймаута
            // eslint-disable-next-line no-console
            console.warn('[billing] polling error:', err);
        }
    }, [billing, stopPolling]);

    const startPolling = useCallback(
        (params?: { targetPlanCode?: string }) => {
            // Каждый старт поллинга увеличивает версию.
            // Это “отменяет” все старые pollOnce, которые ещё могли выполняться.
            runIdRef.current += 1;

            activeTargetRef.current = params?.targetPlanCode ?? targetPlanCode;

            setIsPolling(true);
            setIsTimedOut(false);
            setPollCount(0);

            clearTimers();

            intervalRef.current = setInterval(pollOnce, intervalMs);

            timeoutRef.current = setTimeout(() => {
                if (!mountedRef.current) return;

                // Таймаут относится только к текущему запуску
                stopPolling();
                clearPollingFlag();
                setIsTimedOut(true);
            }, timeoutMs);

            // Сразу делаем первую проверку, чтобы не ждать intervalMs
            void pollOnce();
        },
        [intervalMs, timeoutMs, pollOnce, stopPolling, targetPlanCode, clearTimers],
    );

    useEffect(() => {
        mountedRef.current = true;

        return () => {
            mountedRef.current = false;
            clearTimers();
        };
    }, [clearTimers]);

    /**
     * Возобновляем поллинг после возврата с оплаты:
     * флаг ставится ДО редиректа, а после возвращения мы стартуем один раз.
     */
    useEffect(() => {
        const flag = readFlag();
        if (!flag) return;

        const age = Date.now() - flag.ts;

        // Если флаг старый/битый — просто удаляем
        if (age < 0 || age > flagTtlMs) {
            clearPollingFlag();
            return;
        }

        // Резюмим один раз и сразу очищаем, чтобы не зациклиться
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
