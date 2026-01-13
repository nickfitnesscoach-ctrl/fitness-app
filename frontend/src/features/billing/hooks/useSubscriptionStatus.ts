import type { SubscriptionDetails } from '../../../types/billing';
import { formatDate } from '../utils/date';

interface SubscriptionStatus {
    isPro: boolean;
    isExpired: boolean;
    topStatusText: string;
    headerTitle: string;
    headerSubtitle: string;
}

/**
 * Этот хук НЕ работает с сервером.
 * Он нужен, чтобы:
 * 1) взять "сырые" данные подписки
 * 2) превратить их в понятные флаги и тексты для UI
 *
 * Здесь живёт логика отображения, а не оплаты.
 */
export const useSubscriptionStatus = (
    subscription: SubscriptionDetails | null,
): SubscriptionStatus => {
    /**
     * PRO считается активным только если:
     * - тариф PRO
     * - и подписка помечена как активная
     */
    const isPro = subscription?.plan === 'pro' && subscription?.is_active === true;

    /**
     * Дата окончания нужна и для активной,
     * и для истёкшей подписки
     */
    const expiresAt = subscription?.expires_at ?? null;

    /**
     * Подписка считается истёкшей, если:
     * - PRO сейчас не активен
     * - но дата окончания существует
     */
    const isExpired = !isPro && Boolean(expiresAt);

    /**
     * Тексты шапки экрана.
     * Сейчас они статичны, но вынесены здесь,
     * чтобы вся логика подписки была в одном месте.
     */
    const headerTitle = 'Премиум доступ';
    const headerSubtitle = 'Получи максимум от EatFit24';

    /**
     * Основной статус, который пользователь видит сверху экрана
     */
    let topStatusText = 'Тариф: Базовый';

    if (isPro && expiresAt) {
        topStatusText = `Pro активен до ${formatDate(expiresAt)}`;
    } else if (isExpired && expiresAt) {
        topStatusText = `Истек ${formatDate(expiresAt)}`;
    }

    return {
        isPro,
        isExpired,
        topStatusText,
        headerTitle,
        headerSubtitle,
    };
};
