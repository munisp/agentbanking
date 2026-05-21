/**
 * Haptic feedback utility for mobile/POS interactions.
 * Wraps navigator.vibrate() with named patterns.
 */
type HapticPattern = "tap" | "success" | "error" | "micro" | "warning";

const PATTERNS: Record<HapticPattern, number | number[]> = {
  micro: 5,
  tap: 10,
  success: [15, 50, 15],
  warning: [30, 60, 30],
  error: [50, 100, 50, 100, 50],
};

export function haptic(pattern: HapticPattern = "tap"): void {
  try {
    if (navigator.vibrate) {
      navigator.vibrate(PATTERNS[pattern]);
    }
  } catch {
    // Silently fail on unsupported platforms
  }
}
