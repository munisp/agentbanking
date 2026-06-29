import type { ChallengeType } from "./types";
import { getRegionMotion } from "./motionEngine";

/**
 * Challenge list
 */
export const CHALLENGES: ChallengeType[] = [
  "TURN_LEFT",
  "TURN_RIGHT",
  "BLINK",
  "NOD",
  "SMILE",
];

/**
 * Instructions
 */
export const CHALLENGE_INSTRUCTIONS: Record<ChallengeType, string> = {
  TURN_LEFT: "Turn your head left",
  TURN_RIGHT: "Turn your head right",
  BLINK: "Blink twice",
  NOD: "Nod your head",
  SMILE: "Smile!",
};

/**
 * Generate single challenge
 */
export function generateChallenge(): ChallengeType {
  return CHALLENGES[Math.floor(Math.random() * CHALLENGES.length)];
}

/**
 * Generate sequence
 */
export function generateChallengeSequence(
  count: number = 1
): ChallengeType[] {
  const sequence: ChallengeType[] = [];
  for (let i = 0; i < count; i++) {
    sequence.push(generateChallenge());
  }
  return sequence;
}

/**
 * Get instruction
 */
export function getChallengeInstruction(
  challenge: ChallengeType
): string {
  return CHALLENGE_INSTRUCTIONS[challenge];
}

/**
 * 🔥 Fixed verification (noise-resistant + direction-aware)
 */
export function verifyChallengeResponse(
  challenge: ChallengeType,
  currentMotion: number,
  motionHistory: number[],
  prevFrame?: ImageData,
  currFrame?: ImageData
): boolean {
  if (motionHistory.length < 15) return false;
  console.log(currentMotion)
  const recent = motionHistory.slice(-15);

  const avg =
    recent.reduce((a, b) => a + b, 0) / recent.length;

  const max = Math.max(...recent);

  const baselineSlice = motionHistory.slice(-40, -20);
  const baseline =
    baselineSlice.length > 0
      ? baselineSlice.reduce((a, b) => a + b, 0) /
        baselineSlice.length
      : 0;

  const increase = avg - baseline;

  // Kill noise
  if (max < 0.002 && avg < 0.0015) return false;

  // Consistency
  const activeFrames = recent.filter((m) => m > avg * 0.7).length;
  const consistency = activeFrames / recent.length;

  if (consistency < 0.3) return false;

  // Region motion
  let left = 0;
  let right = 0;

  if (prevFrame && currFrame) {
    left = getRegionMotion(prevFrame, currFrame, "left");
    right = getRegionMotion(prevFrame, currFrame, "right");
  }

  switch (challenge) {
    case "TURN_LEFT":
      return (
        right > left * 1.4 &&
        (increase > 0.002 || max > 0.006)
      );

    case "TURN_RIGHT":
      return (
        left > right * 1.4 &&
        (increase > 0.002 || max > 0.006)
      );

    case "NOD": {
      const variance =
        recent.reduce(
          (sum, m) => sum + Math.pow(m - avg, 2),
          0
        ) / recent.length;

      return (
        variance > 0.00004 &&
        increase > 0.002 &&
        consistency > 0.4
      );
    }

    case "BLINK":
      return (
        max > avg * 2.2 &&
        max > 0.004 &&
        consistency < 0.6
      );

    case "SMILE":
      return (
        avg > 0.003 &&
        increase > 0.0015 &&
        consistency > 0.5
      );

    default:
      return false;
  }
}