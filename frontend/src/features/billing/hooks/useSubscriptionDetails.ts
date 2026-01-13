import { useMemo, useRef, useState } from 'react';
import { useBilling } from '../../../contexts/BillingContext';
import { useAuth } from '../../../contexts/AuthContext';
import { api } from '../../../services/api';
import { formatShortDate } from '../utils/date';
import { showToast } from '../utils/notify';
import type { SubscriptionDetails } from '../../../types/billing';

interface UseSubscriptionDetailsResult {
    subscription: SubscriptionDetails | null;
    isPro: boolean;
    expiresAtFormatted: string;
    autoRenewEnabled: boolean;
    autoRenewAvailable: boolean;
    hasCard: boolean;
    cardInfoLabel: string;

    isAdmin: boolean;
    testLivePaymentAvailable: boolean;
    togglingAutoRenew: boolean;
    creatingTestPayment: boolean;

    handleToggleAutoRenew: () => Promise<void>;
    handlePaymentMethodClick: () => Promise<void>;
    handleCreateTestPayment: () => Promise<void>;
}

/**
 * Маленький helper: достаём “человеческое сообщение” из ошибки.
 * Зачем: сервер иногда кладёт JSON в error.message, а иногда — обычный текст.
 * Мы хотим показать пользователю одно понятное сообщение, без тех.подробностей.
 */
function getReadableErrorMessage(error: unknown, fallback: string): string {
    if (!(error instanceof Error)) return fallback;

    const raw = (error.message || '').trim();
    if (!raw) return fallback;

    // Если message выглядит как JSON — попробуем вытащить data.message
    if (raw.startsWith('{') && raw.endsWith('}')) {
        try {
            const data = JSON.parse(raw);
            if (typeof data?.message === 'string' && data.message.trim()) return data.message.trim();
        } catch {
            // ignore
        }
    }

    return raw || fallback;
}

/**
 * Маленький helper: “внутри Telegram Mini App” или нет.
 * Зачем: в TMA правильнее открывать ссылки через Telegram.WebApp.openLink().
 */
function isTelegramMiniApp(): boolean {
    return typeof window !== 'undefined' && Boolean(window.Telegram?.WebApp?.initData);
}

export const useSubscriptionDetails = (): UseSubscriptionDetailsResult => {
    const billing = useBilling();
    const auth = useAuth();

    const [togglingAutoRenew, setTogglingAutoRenew] = useState(false);
    const [creatingTestPayment, setCreatingTestPayment] = useState(false);

    /**
     * Лок “защита от двойных кликов” (и гонок между быстрыми нажатиями).
     * Мы не даём запустить одно и то же действие повторно, пока оно не закончится.
     */
    const inFlightRef = useRef<Set<string>>(new Set());

    const subscription = billing.subscription;

    const isPro = subscription?.plan === 'pro';
    const expiresAt = subscription?.expires_at ?? null;

    /**
     * Важно: formatShortDate() должна уметь обрабатывать null,
     * иначе здесь надо будет дать безопасный fallback.
     * Сейчас НЕ меняю поведение, чтобы не “сломать привычный UI”.
     */
    const expiresAtFormatted = formatShortDate(expiresAt);

    const autoRenewEnabled = subscription?.autorenew_enabled ?? false;
    const autoRenewAvailable = subscription?.autorenew_available ?? false;

    const paymentMethod = subscription?.payment_method;
    const hasCard = paymentMethod?.is_attached ?? false;

    const isAdmin = auth.isAdmin ?? false;
    const testLivePaymentAvailable = billing.billingMe?.test_live_payment_available ?? false;

    const cardInfoLabel = useMemo(() => {
        // Если карты нет — показываем простую фразу, чтобы пользователь понял “что делать дальше”
        if (!hasCard || !paymentMethod) return 'Карта не привязана';

        // Маска и бренд — это “приятная деталь”, но если сервер их не вернул,
        // UI всё равно должен остаться аккуратным.
        const mask = paymentMethod.card_mask || '••••';
        const brand = paymentMethod.card_brand || 'Card';

        return `${mask} · ${brand}`;
    }, [hasCard, paymentMethod]);

    const handleToggleAutoRenew = async (): Promise<void> => {
        const lockKey = 'autorenew:toggle';

        // Защита от повторного нажатия (и от дубля на слабых девайсах)
        if (togglingAutoRenew || inFlightRef.current.has(lockKey)) return;

        // “Автопродление доступно” обычно означает: есть привязанная карта
        if (!autoRenewAvailable) {
            showToast('Автопродление недоступно — привяжите карту');
            return;
        }

        inFlightRef.current.add(lockKey);
        setTogglingAutoRenew(true);

        try {
            // Важно: мы переключаем на противоположное значение текущего состояния
            await billing.setAutoRenew(!autoRenewEnabled);

            showToast(autoRenewEnabled ? 'Автопродление отключено' : 'Автопродление включено');
        } catch (error) {
            // eslint-disable-next-line no-console
            console.error('[billing] setAutoRenew error:', error);

            showToast(getReadableErrorMessage(error, 'Не удалось изменить настройки'));
        } finally {
            setTogglingAutoRenew(false);
            inFlightRef.current.delete(lockKey);
        }
    };

    const handlePaymentMethodClick = async (): Promise<void> => {
        const lockKey = 'payment-method:click';
        if (inFlightRef.current.has(lockKey)) return;

        // Пока смену карты не поддерживаем: если карта уже есть — честно говорим об этом
        if (hasCard) {
            showToast('Смена карты будет доступна позже');
            return;
        }

        inFlightRef.current.add(lockKey);

        try {
            // Запускает привязку карты (обычно открывает страницу/редиректит)
            await billing.addPaymentMethod();
        } catch (error) {
            // eslint-disable-next-line no-console
            console.error('[billing] addPaymentMethod error:', error);

            showToast(getReadableErrorMessage(error, 'Ошибка при запуске привязки карты'));
        } finally {
            inFlightRef.current.delete(lockKey);
        }
    };

    const handleCreateTestPayment = async (): Promise<void> => {
        const lockKey = 'admin:test-payment';

        if (creatingTestPayment || inFlightRef.current.has(lockKey)) return;

        // Защита “на всякий случай”: даже если кнопку случайно показали, действие не выполнится без прав
        if (!isAdmin || !testLivePaymentAvailable) {
            showToast('Недостаточно прав');
            return;
        }

        inFlightRef.current.add(lockKey);
        setCreatingTestPayment(true);

        try {
            // API может вернуть ссылку подтверждения платежа
            const res: any = await api.createTestLivePayment();
            const url = res?.confirmation_url;

            if (typeof url === 'string' && url.length > 0) {
                if (isTelegramMiniApp() && window.Telegram?.WebApp?.openLink) {
                    window.Telegram.WebApp.openLink(url);
                } else {
                    window.location.href = url;
                }
            }
        } catch (error) {
            // eslint-disable-next-line no-console
            console.error('[billing] createTestLivePayment error:', error);

            showToast(getReadableErrorMessage(error, 'Ошибка при создании тестового платежа'));
        } finally {
            setCreatingTestPayment(false);
            inFlightRef.current.delete(lockKey);
        }
    };

    return {
        subscription,
        isPro,
        expiresAtFormatted,
        autoRenewEnabled,
        autoRenewAvailable,
        hasCard,
        cardInfoLabel,

        isAdmin,
        testLivePaymentAvailable,
        togglingAutoRenew,
        creatingTestPayment,

        handleToggleAutoRenew,
        handlePaymentMethodClick,
        handleCreateTestPayment,
    };
};
