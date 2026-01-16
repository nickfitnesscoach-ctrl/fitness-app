import { useEffect } from "react";

/**
 * Reference-counted body scroll lock for iOS/Telegram WebView.
 *
 * Features:
 * - Uses position:fixed (not just overflow:hidden) for iOS compatibility
 * - Reference-counted: supports nested modals safely
 * - Preserves scroll position across lock/unlock cycles
 *
 * Usage:
 *   useBodyScrollLock(isOpen)  // preferred: pass open state
 *   useBodyScrollLock(true)    // OK if component unmounts when closed
 */

let lockCount = 0;
let savedScrollY = 0;

function applyLock() {
  const body = document.body;
  const html = document.documentElement;

  body.style.position = "fixed";
  body.style.top = `-${savedScrollY}px`;
  body.style.left = "0";
  body.style.right = "0";
  body.style.width = "100%";
  body.style.overflow = "hidden";

  html.classList.add("modal-open");
  body.classList.add("modal-open");
}

function removeLock() {
  const body = document.body;
  const html = document.documentElement;

  body.style.position = "";
  body.style.top = "";
  body.style.left = "";
  body.style.right = "";
  body.style.width = "";
  body.style.overflow = "";

  html.classList.remove("modal-open");
  body.classList.remove("modal-open");

  window.scrollTo(0, savedScrollY);
}

export function useBodyScrollLock(isOpen: boolean) {
  useEffect(() => {
    if (!isOpen) return;

    // First lock: save scroll position
    if (lockCount === 0) {
      savedScrollY = window.scrollY;
      applyLock();
    }
    lockCount++;

    return () => {
      lockCount--;
      // Last unlock: restore scroll position
      if (lockCount === 0) {
        removeLock();
      }
    };
  }, [isOpen]);
}
