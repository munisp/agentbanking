/**
 * Scoring Engine
 * Aggregates all signals and computes final liveness score
 */

import type { LivenessSignals } from "./types";

export interface SignalInputs {
  motion: number;
  challengePassed: boolean;
  timingVariance: number;
  lightVariance: number;
  frameDiff: number;
  jitter?: number;
  flicker?: number;
}

export function scoreEngine(inputs: SignalInputs): LivenessSignals {
  let score = 0;

  // Motion score: 30% weight - require intentional movement
  if (inputs.motion > 0.015) {
    score += 0.3;
  } else if (inputs.motion > 0.008) {
    score += 0.15;
  }

  // Challenge passed: 40% weight - most important
  if (inputs.challengePassed) {
    score += 0.4;
  }

  // Timing variance: 10% weight - less critical
  if (inputs.timingVariance >= 0) {
    score += 0.1;
  }

  // Light variance: 10% weight
  if (inputs.lightVariance > 0.005) {
    score += 0.1;
  } else if (inputs.lightVariance > 0) {
    score += 0.05;
  }

  // Frame diff: 10% weight - should have some difference
  if (inputs.frameDiff > 0.005) {
    score += 0.1;
  } else if (inputs.frameDiff > 0.001) {
    score += 0.05;
  }

  return {
    motion: inputs.motion,
    challengePassed: inputs.challengePassed,
    timingVariance: inputs.timingVariance,
    lightVariance: inputs.lightVariance,
    frameDiff: inputs.frameDiff,
    score: Math.min(score, 1),
  };
}

export function getVerdict(
  score: number,
  threshold: number = 0.5,
): "VERIFIED" | "REJECTED" {
  return score >= threshold ? "VERIFIED" : "REJECTED";
}

export function analyzeSignals(signals: LivenessSignals): {
  strengths: string[];
  weaknesses: string[];
  recommendations: string[];
} {
  const strengths: string[] = [];
  const weaknesses: string[] = [];
  const recommendations: string[] = [];

  if (signals.motion > 0.1) {
    strengths.push("Good motion detected");
  } else {
    weaknesses.push("Low motion detected");
    recommendations.push("Move your head more naturally");
  }

  if (signals.challengePassed) {
    strengths.push("Challenge completed successfully");
  } else {
    weaknesses.push("Challenge not completed");
    recommendations.push("Follow the instructions carefully");
  }

  if (signals.timingVariance < 0.5) {
    strengths.push("Natural timing");
  } else {
    weaknesses.push("Unusual timing pattern");
    recommendations.push("Respond at a natural pace");
  }

  if (signals.lightVariance > 0.1) {
    strengths.push("Good lighting conditions");
  } else {
    weaknesses.push("Poor lighting variance");
    recommendations.push("Ensure proper lighting");
  }

  if (signals.frameDiff > 0.02) {
    strengths.push("Dynamic scene detected");
  } else {
    weaknesses.push("Static scene detected");
    recommendations.push("Move naturally");
  }

  return { strengths, weaknesses, recommendations };
}
