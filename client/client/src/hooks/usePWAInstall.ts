/**
 * usePWAInstall — Captures the browser's beforeinstallprompt event
 * and exposes a function to trigger the native PWA install dialog.
 *
 * Usage:
 *   const { canInstall, install, isInstalled } = usePWAInstall();
 *   if (canInstall) <button onClick={install}>Install App</button>
 */
import { useState, useEffect, useCallback } from "react";

interface BeforeInstallPromptEvent extends Event {
  readonly platforms: string[];
  readonly userChoice: Promise<{
    outcome: "accepted" | "dismissed";
    platform: string;
  }>;
  prompt(): Promise<void>;
}

export interface PWAInstallState {
  /** True if the browser supports installation and hasn't been installed yet */
  canInstall: boolean;
  /** True if the app is already running in standalone/PWA mode */
  isInstalled: boolean;
  /** Triggers the native install prompt. Returns true if user accepted. */
  install: () => Promise<boolean>;
}

export function usePWAInstall(): PWAInstallState {
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null);
  const [canInstall, setCanInstall] = useState(false);

  // Check if already running as installed PWA
  const isInstalled =
    typeof window !== "undefined" &&
    (window.matchMedia("(display-mode: standalone)").matches ||
      (window.navigator as Navigator & { standalone?: boolean }).standalone ===
        true);

  useEffect(() => {
    const handler = (e: Event) => {
      e.preventDefault();
      setDeferredPrompt(e as BeforeInstallPromptEvent);
      setCanInstall(true);
    };

    window.addEventListener("beforeinstallprompt", handler);

    // Also listen for successful install to hide the button
    window.addEventListener("appinstalled", () => {
      setCanInstall(false);
      setDeferredPrompt(null);
    });

    return () => {
      window.removeEventListener("beforeinstallprompt", handler);
    };
  }, []);

  const install = useCallback(async (): Promise<boolean> => {
    if (!deferredPrompt) return false;
    await deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    if (outcome === "accepted") {
      setCanInstall(false);
      setDeferredPrompt(null);
    }
    return outcome === "accepted";
  }, [deferredPrompt]);

  return { canInstall: canInstall && !isInstalled, isInstalled, install };
}
