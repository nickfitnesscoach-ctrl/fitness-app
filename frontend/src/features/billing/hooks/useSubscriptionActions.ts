import { useCallback, useRef, useState } from 'react';
import type { SubscriptionPlan } from '../../../types/billing';
import type { PlanCode } from '../types';
import { api } from '../../../services/api';
import { useBilling } from '../../../contexts/BillingContext';
import { showToast } from '../utils/notify';
import { setPollingFlagForPayment } from './usePaymentPolling';

interface UseSubscriptionActionsParams {
    plans: SubscriptionPlan[];
    isBrowserDebug: boolean;
    webAppBrowserDebug: boolean;
}

interface UseSubscriptionActionsResult {
    loadingPlanCode: PlanCode | null;
    togglingAutoRenew: boolean;
    handleSelectPlan: (planCode: PlanCode) => Promise<void>;
    handleToggleAutoRenew: () => Promise<void>;
    handleAddCard: () => Promise<void>;
}

/**
 * Мы открываем ссылку оплаты во внешнем браузере/вкладке.
 * Поэтому здесь обязательно держим tight allowlist по доменам,
 * чтобы никакой серверный/клиентский баг не превратился в фишинг.
 */
const PAYMENT_URL_ALLOWLIST = [
    'yookassa.ru',
    'checkout.yookassa.ru',
    'yoomoney.ru',
];

function isAllowedPaymentUrl(rawUrl: string): boolean {
    try {
        const u = new URL(rawUrl);
        if (u.protocol !== 'https:') return false;

        const host = u.hostname.toLowerCase();
        return PAYMENT_URL_ALLOWLIST.some((allowed) => host === allowed || host.endsWith(`.${allowed}`));
    } catch {
        return false;
    }
}

/**
 * Открываем ссылку корректно и в Telegram Mini App, и в обычном браузере.
 * В TMA важно использовать openLink, иначе Telegram может “съесть” переход.
 */
function openExternalLink(url: string): void {
    const isTMA = typeof window !== 'undefined' && Boolean(window.Telegram?.WebApp?.initData);

    if (isTMA && window.Telegram?.WebApp?.openLink) {
        window.Telegram.WebApp.openLink(url);
        return;
    }

    window.location.href = url;
}

/**
 * Достаём понятное сообщение из ошибки.
 * Иногда backend кладёт JSON в error.message — поддерживаем это.
 */
function getReadableErrorMessage(error: unknown, fallback: string): string {
    if (!(error instanceof Error)) return fallback;

    const raw = (error.message || '').trim();
    if (!raw) return fallback;

    // поддержка structured JSON: {"message": "..."}
    if (raw.startsWith('{') && raw.endsWith('}')) {
        try {
            const data = JSON.parse(raw);
            if (typeof data?.message === 'string' && data.message.trim()) {
                return data.message.trim();
            }
        } catch {
            // ignore
        }
    }

    return raw || fallback;
}

export const useSubscriptionActions = ({
    plans,
    isBrowserDebug,
    webAppBrowserDebug,
}: UseSubscriptionActionsParams): UseSubscriptionActionsResult => {
    const billing = useBilling();

    /**
     * loadingPlanCode — это чисто UI-индикатор:
     * какой тариф сейчас “крутит спиннер”.
     * Логику защиты от дублей делает withLock.
     */
    const [loadingPlanCode, setLoadingPlanCode] = useState<PlanCode | null>(null);

    /**
     * togglingAutoRenew — общий индикатор “идёт важное действие с подпиской/картой”.
     * Сейчас он используется и для toggle, и для bind-card — поведение сохраняем.
     */
    const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);

    /**
     * Защита от двойного клика и параллельных запросов.
     * Важно: ключи разные для разных действий.
     */
    const inFlightRef = useRef<Set<string>>(new Set());

    const withLock = useCallback(async (key: string, fn: () => Promise<void>) => {
        if (inFlightRef.current.has(key)) return;

        inFlightRef.current.add(key);
        try {
            await fn();
        } finally {
            inFlightRef.current.delete(key);
        }
    }, []);

    const handleSelectPlan = useCallback(
        async (planCode: PlanCode) => {
            // В debug-режимах оплату блокируем, чтобы случайно не провести реальный платеж.
            if (isBrowserDebug || webAppBrowserDebug) {
                showToast('Платежи недоступны в режиме отладки браузера');
                return;
            }

            const lockKey = `payment:${planCode}`;

            await withLock(lockKey, async () => {
                const plan = plans.find((p) => p.code === planCode);
                if (!plan) {
                    showToast('Тариф не найден');
                    return;
                }

                // Показываем в UI, что именно этот тариф “в процессе оплаты”
                setLoadingPlanCode(planCode);

                try {
                    const { confirmation_url } = await api.createPayment({
                        plan_code: planCode,
                        save_payment_method: true,
                    });

                    if (!confirmation_url || typeof confirmation_url !== 'string') {
                        showToast('Не удалось получить ссылку на оплату');
                        return;
                    }

                    // SECURITY: защита от открытого редиректа / подмены ссылки
                    if (!isAllowedPaymentUrl(confirmation_url)) {
                        showToast('Некорректная ссылка оплаты. Попробуйте позже.');
                        return;
                    }

                    /**
                     * Флаг поллинга ставим ДО редиректа:
                     * чтобы когда пользователь вернётся — мы знали, что нужно проверить статус платежа.
                     */
                    setPollingFlagForPayment({ targetPlanCode: planCode });

                    openExternalLink(confirmation_url);
                } catch (error) {
                    // eslint-disable-next-line no-console
                    console.error('[billing] createPayment error:', error);

                    showToast(getReadableErrorMessage(error, 'Ошибка при оформлении подписки'));
                } finally {
                    setLoadingPlanCode(null);
                }
            });
        },
        [isBrowserDebug, webAppBrowserDebug, withLock, plans],
    );

    const handleToggleAutoRenew = useCallback(async () => {
        const lockKey = 'autorenew:toggle';

        await withLock(lockKey, async () => {
            if (togglingAutoRenew) return;

            /**
             * SSOT — текущее состояние в billing.subscription.
             * Мы берём значения прямо перед действием,
             * чтобы не переключать “устаревшее” состояние.
             */
            const current = billing.subscription;
            const autoRenewAvailable = current?.autorenew_available ?? false;
            const autoRenewEnabled = current?.autorenew_enabled ?? false;

            if (!autoRenewAvailable) {
                showToast('Автопродление недоступно — привяжите карту');
                return;
            }

            setTogglingAutoRenew(true);
            try {
                await billing.setAutoRenew(!autoRenewEnabled);
                showToast(autoRenewEnabled ? 'Автопродление отключено' : 'Автопродление включено');
            } catch (error) {
                // eslint-disable-next-line no-console
                console.error('[billing] setAutoRenew error:', error);

                showToast('Не удалось изменить настройки автопродления');
            } finally {
                setTogglingAutoRenew(false);
            }
        });
    }, [withLock, togglingAutoRenew, billing]);

    const handleAddCard = useCallback(async () => {
        const lockKey = 'card:bind';

        await withLock(lockKey, async () => {
            if (togglingAutoRenew) return;

            setTogglingAutoRenew(true);
            try {
                /**
                 * addPaymentMethod обычно сам делает редирект/открытие страницы привязки.
                 * Поэтому тут просто вызываем и обрабатываем ошибку.
                 */
                await billing.addPaymentMethod();
            } catch (error) {
                // eslint-disable-next-line no-console
                console.error('[billing] addPaymentMethod error:', error);

                showToast(getReadableErrorMessage(error, 'Не удалось запустить привязку карты'));
            } finally {
                setTogglingAutoRenew(false);
            }
        });
    }, [withLock, togglingAutoRenew, billing]);

    return {
        loadingPlanCode,
        togglingAutoRenew,
        handleSelectPlan,
        handleToggleAutoRenew,
        handleAddCard,
    };
};
