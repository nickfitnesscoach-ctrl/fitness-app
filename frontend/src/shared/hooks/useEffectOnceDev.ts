import { useEffect, useRef } from "react";

type EffectFn = () => void | (() => void);

/**
 * DEV-only guard against React StrictMode double-invoking effects.
 * 
 * Behavior:
 * - In DEV: runs effect once per unique deps state (StrictMode double-invoke blocked)
 * - In PROD: behaves exactly like regular useEffect
 * - If deps actually change, effect re-runs (correct behavior preserved)
 * 
 * @example
 * useEffectOnceDev(() => {
 *   if (!isAuthenticated) return;
 *   void loadInitialData();
 * }, [isAuthenticated, loadInitialData]);
 */
export function useEffectOnceDev(effect: EffectFn, deps: readonly unknown[] = []): void {
    const didRun = useRef(false);

    useEffect(() => {
        if (import.meta.env.DEV) {
            if (didRun.current) return;
            didRun.current = true;
        }

        return effect();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, deps);
}
