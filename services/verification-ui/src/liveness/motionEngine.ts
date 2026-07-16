/**
 * Motion Engine
 * Detects general movement, natural jitter, and micro motion
 */







export function isMoving(score: number, threshold: number = 0.01): boolean {
  return score > threshold;
}
export function motionScore(prev: ImageData, curr: ImageData): number {
  let diff = 0;
  const sampleRate = 2;

  for (let i = 0; i < curr.data.length; i += sampleRate * 4) {
    const r = Math.abs(curr.data[i] - prev.data[i]);
    const g = Math.abs(curr.data[i + 1] - prev.data[i + 1]);
    const b = Math.abs(curr.data[i + 2] - prev.data[i + 2]);

    const avg = (r + g + b) / 3;

    // 🔥 Ignore micro-noise
    if (avg < 8) continue;

    diff += avg;
  }

  const maxDiff = (curr.data.length / (sampleRate * 4)) * 255;
  return Math.min(diff / maxDiff, 1);
}

// 🔥 Region-based motion (left/right)
export function getRegionMotion(
  prev: ImageData,
  curr: ImageData,
  region: "left" | "right"
): number {
  const width = curr.width;
  const height = curr.height;

  let startX = region === "left" ? 0 : Math.floor(width / 2);
  let endX = region === "left" ? Math.floor(width / 2) : width;

  let diff = 0;

  for (let y = 0; y < height; y += 2) {
    for (let x = startX; x < endX; x += 2) {
      const i = (y * width + x) * 4;

      const r = Math.abs(curr.data[i] - prev.data[i]);
      const g = Math.abs(curr.data[i + 1] - prev.data[i + 1]);
      const b = Math.abs(curr.data[i + 2] - prev.data[i + 2]);

      const avg = (r + g + b) / 3;

      if (avg > 8) diff += avg;
    }
  }

  return diff;
}

// 🔥 Motion consistency (human vs noise)
export function motionConsistency(history: number[]): number {
  if (history.length < 10) return 0;

  let consistent = 0;

  for (let i = 1; i < history.length; i++) {
    const diff = Math.abs(history[i] - history[i - 1]);
    if (diff < 0.01) consistent++;
  }

  return consistent / history.length;
}

// 🔥 Natural pattern check
export function hasNaturalMotionPattern(history: number[]): boolean {
  if (history.length < 15) return false;

  let spikes = 0;

  for (let i = 1; i < history.length; i++) {
    const jump = Math.abs(history[i] - history[i - 1]);
    if (jump > 0.05) spikes++;
  }

  return spikes < history.length * 0.3;
}