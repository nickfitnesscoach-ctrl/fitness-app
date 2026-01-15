/**
 * UUID generation utility with fallback for older browsers
 *
 * Modern browsers support crypto.randomUUID(), but for compatibility
 * we provide a fallback implementation.
 */

/**
 * Generate a UUID v4 string.
 * Uses crypto.randomUUID() if available, otherwise falls back to
 * a compliant UUID v4 implementation using crypto.getRandomValues().
 *
 * @returns UUID v4 string (e.g., "550e8400-e29b-41d4-a716-446655440000")
 */
export function generateUUID(): string {
    // Modern browsers support crypto.randomUUID()
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
        return crypto.randomUUID();
    }

    // Fallback: UUID v4 implementation
    // Format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
    // where x is any hexadecimal digit and y is one of 8, 9, A, or B
    if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
        const bytes = new Uint8Array(16);
        crypto.getRandomValues(bytes);

        // Set version (4) and variant (RFC4122)
        bytes[6] = (bytes[6] & 0x0f) | 0x40; // Version 4
        bytes[8] = (bytes[8] & 0x3f) | 0x80; // Variant 10

        const hex = Array.from(bytes)
            .map((b) => b.toString(16).padStart(2, '0'))
            .join('');

        return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}`;
    }

    // Last resort fallback (should never happen in modern environments)
    // This is NOT cryptographically secure but ensures the app doesn't crash
    console.warn('[generateUUID] crypto API not available, using insecure fallback');
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
        const r = (Math.random() * 16) | 0;
        const v = c === 'x' ? r : (r & 0x3) | 0x8;
        return v.toString(16);
    });
}
