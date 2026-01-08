/**
 * Date formatting utilities for billing module
 * Single source of truth for all billing date formatting
 */

/**
 * Formats date with time for payment history display
 * Example: "20 дек. 2025, 14:30"
 */
export const formatBillingDate = (dateString: string | null | undefined): string => {
    if (!dateString) return '—';
    return new Date(dateString).toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
};

/**
 * Formats date as DD.MM.YYYY for subscription expiry display
 * Example: "20.12.2025"
 */
export const formatShortDate = (dateString: string | null | undefined): string => {
    if (!dateString) return '';
    return new Date(dateString).toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'numeric',
        year: 'numeric',
    });
};

/**
 * Alias for formatShortDate - used in plan card state
 * Kept for semantic clarity in different contexts
 */
export const formatDate = formatShortDate;
