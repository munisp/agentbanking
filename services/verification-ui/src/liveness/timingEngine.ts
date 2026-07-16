/**
 * Timing Engine
 * Analyzes timing variance and response patterns
 */

export function timingVariance(startTime: number, actionTime: number): number {
  const elapsed = actionTime - startTime;

  // Expected response time: 1-5 seconds
  const minExpected = 1000;
  const maxExpected = 5000;

  if (elapsed < minExpected) {
    // Too fast - suspicious
    return Math.abs(minExpected - elapsed) / minExpected;
  } else if (elapsed > maxExpected) {
    // Too slow - suspicious
    return Math.abs(elapsed - maxExpected) / maxExpected;
  }

  // Within expected range - calculate normalized variance
  const ideal = (minExpected + maxExpected) / 2;
  return Math.abs(elapsed - ideal) / ideal;
}

export function isTimingNatural(
  variance: number,
  threshold: number = 0.5,
): boolean {
  return variance <= threshold;
}

export function calculateResponseTime(
  startTime: number,
  endTime: number,
): number {
  return endTime - startTime;
}

export function analyzeTimingPattern(timings: number[]): {
  average: number;
  variance: number;
  isNatural: boolean;
} {
  if (timings.length === 0) {
    return { average: 0, variance: 0, isNatural: false };
  }

  const average = timings.reduce((a, b) => a + b, 0) / timings.length;

  let variance = 0;
  timings.forEach((timing) => {
    variance += Math.pow(timing - average, 2);
  });
  variance = Math.sqrt(variance / timings.length);

  // Natural human response has some variance (not robotic)
  const isNatural = variance > 100 && variance < 2000;

  return { average, variance, isNatural };
}
