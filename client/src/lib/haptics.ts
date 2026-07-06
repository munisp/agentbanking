/**
 * Haptic Feedback Utility (PWA)
 * Matches Flutter/RN haptic patterns:
 * - success: double pulse (50ms-30ms-50ms)
 * - failure: long buzz (300ms)
 * - warning: three short (30ms-20ms-30ms-20ms-30ms)
 * - selection: single tick (10ms)
 *
 * Falls back silently on devices without vibration support.
 */

const supportsVibration = typeof navigator !== "undefined" && "vibrate" in navigator;

export function hapticSuccess(): void {
  if (!supportsVibration) return;
  navigator.vibrate([50, 30, 50]);
}

export function hapticFailure(): void {
  if (!supportsVibration) return;
  navigator.vibrate(300);
}

export function hapticWarning(): void {
  if (!supportsVibration) return;
  navigator.vibrate([30, 20, 30, 20, 30]);
}

export function hapticSelection(): void {
  if (!supportsVibration) return;
  navigator.vibrate(10);
}

export function hapticNotification(): void {
  if (!supportsVibration) return;
  navigator.vibrate([100, 50, 100]);
}

type HapticType = "micro" | "tap" | "success" | "error" | "warning" | "selection" | "notification" | "failure";

const hapticMap: Record<HapticType, () => void> = {
  micro: hapticSelection,
  tap: hapticSelection,
  success: hapticSuccess,
  error: hapticFailure,
  failure: hapticFailure,
  warning: hapticWarning,
  selection: hapticSelection,
  notification: hapticNotification,
};

export function haptic(type: HapticType): void {
  hapticMap[type]?.();
}
