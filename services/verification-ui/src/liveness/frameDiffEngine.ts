/**
 * Frame Diff Engine
 * Detects static spoof and replay video patterns
 */

export function frameDiff(a: ImageData, b: ImageData): number {
  let sum = 0;
  const sampleRate = 4; // Sample every 4th pixel for performance

  for (let i = 0; i < a.data.length; i += sampleRate * 4) {
    const rDiff = Math.abs(a.data[i] - b.data[i]);
    const gDiff = Math.abs(a.data[i + 1] - b.data[i + 1]);
    const bDiff = Math.abs(a.data[i + 2] - b.data[i + 2]);
    sum += (rDiff + gDiff + bDiff) / 3;
  }

  // Normalize to 0-1 range
  const maxDiff = (a.data.length / (sampleRate * 4)) * 255;
  return Math.min(sum / maxDiff, 1);
}

export function detectReplayPattern(diffHistory: number[]): boolean {
  if (diffHistory.length < 5) return false;

  // Check for repeating patterns (simple implementation)
  const mean = diffHistory.reduce((a, b) => a + b, 0) / diffHistory.length;
  const lowVariance = diffHistory.every((val) => Math.abs(val - mean) < 0.01);

  // If all diffs are nearly identical, might be replay
  return lowVariance && mean > 0.02;
}

export function isStaticImage(
  diffScore: number,
  threshold: number = 0.005,
): boolean {
  return diffScore < threshold;
}
