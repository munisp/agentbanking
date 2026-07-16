/**
 * Light Engine
 * Detects screen replay, light flicker, and RGB variance
 */

export function lightVariance(frame: ImageData): number {
  let variance = 0;
  const sampleRate = 8; // Sample every 8th pixel for performance

  for (let i = 0; i < frame.data.length; i += sampleRate * 4) {
    const r = frame.data[i];
    const g = frame.data[i + 1];
    const b = frame.data[i + 2];

    // Calculate variance between color channels
    const mean = (r + g + b) / 3;
    variance += Math.abs(r - mean) + Math.abs(g - mean) + Math.abs(b - mean);
  }

  // Normalize to 0-1 range
  const maxVariance = (frame.data.length / (sampleRate * 4)) * 255 * 3;
  return Math.min(variance / maxVariance, 1);
}

export function detectScreenFlicker(brightnessHistory: number[]): number {
  if (brightnessHistory.length < 5) return 0;

  let flickerScore = 0;
  for (let i = 1; i < brightnessHistory.length; i++) {
    const change = Math.abs(brightnessHistory[i] - brightnessHistory[i - 1]);
    flickerScore += change;
  }

  // Normalize and return flicker score
  return Math.min(flickerScore / brightnessHistory.length, 1);
}

export function getAverageBrightness(frame: ImageData): number {
  let brightness = 0;
  const sampleRate = 8;

  for (let i = 0; i < frame.data.length; i += sampleRate * 4) {
    const r = frame.data[i];
    const g = frame.data[i + 1];
    const b = frame.data[i + 2];
    brightness += (r + g + b) / 3;
  }

  const samples = frame.data.length / (sampleRate * 4);
  return brightness / (samples * 255); // Normalized to 0-1
}
