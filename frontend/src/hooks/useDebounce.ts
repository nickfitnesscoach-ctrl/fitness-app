/**
 * F-022: Debounce hook for preventing rapid repeated actions
 */

import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Debounce a value - returns the value after delay ms of no changes
 */
export function useDebounce<T>(value: T, delay: number): T {
    const [debouncedValue, setDebouncedValue] = useState<T>(value);

    useEffect(() => {
        const timer = setTimeout(() => {
            setDebouncedValue(value);
        }, delay);

        return () => {
            clearTimeout(timer);
        };
    }, [value, delay]);

    return debouncedValue;
}

/**
 * Debounced callback - calls the function after delay ms of no invocations
 */
export function useDebouncedCallback<T extends (...args: any[]) => any>(
    callback: T,
    delay: number
): T {
    const timeoutRef = useRef<NodeJS.Timeout | null>(null);
    const callbackRef = useRef(callback);

    // Update callback ref on each render
    useEffect(() => {
        callbackRef.current = callback;
    }, [callback]);

    const debouncedCallback = useCallback(
        (...args: Parameters<T>) => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }

            timeoutRef.current = setTimeout(() => {
                callbackRef.current(...args);
            }, delay);
        },
        [delay]
    ) as T;

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, []);

    return debouncedCallback;
}

/**
 * Button click guard - prevents double-clicks and rapid repeated clicks
 * Returns [isDisabled, guardedHandler]
 */
export function useButtonGuard(
    handler: () => void | Promise<void>,
    cooldownMs: number = 500
): [boolean, () => void] {
    const [isDisabled, setIsDisabled] = useState(false);
    const timeoutRef = useRef<NodeJS.Timeout | null>(null);

    const guardedHandler = useCallback(() => {
        if (isDisabled) return;

        setIsDisabled(true);
        
        const result = handler();
        
        if (result instanceof Promise) {
            result.finally(() => {
                // Re-enable after cooldown
                timeoutRef.current = setTimeout(() => {
                    setIsDisabled(false);
                }, cooldownMs);
            });
        } else {
            timeoutRef.current = setTimeout(() => {
                setIsDisabled(false);
            }, cooldownMs);
        }
    }, [handler, cooldownMs, isDisabled]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, []);

    return [isDisabled, guardedHandler];
}
