/**
 * Haptic feedback helpers backed by the Vibration API (no-op on devices
 * without vibration support).
 */

export type HapticKind =
  | "light"
  | "medium"
  | "heavy"
  | "micro"
  | "tap"
  | "success"
  | "error";

const PATTERNS: Record<HapticKind, number | number[]> = {
  micro: 10,
  light: 15,
  tap: 20,
  medium: 30,
  heavy: 50,
  success: [20, 40, 20],
  error: [50, 60, 50],
};

function vibrate(pattern: number | number[]) {
  if (typeof navigator !== "undefined" && "vibrate" in navigator) {
    try {
      navigator.vibrate(pattern);
    } catch {
      // vibration not permitted — ignore
    }
  }
}

export const haptics = {
  micro: () => vibrate(PATTERNS.micro),
  light: () => vibrate(PATTERNS.light),
  tap: () => vibrate(PATTERNS.tap),
  medium: () => vibrate(PATTERNS.medium),
  heavy: () => vibrate(PATTERNS.heavy),
  success: () => vibrate(PATTERNS.success),
  error: () => vibrate(PATTERNS.error),
};

/** Trigger a haptic pulse by name. */
export function haptic(kind: HapticKind = "light") {
  haptics[kind]();
}

export default haptics;
