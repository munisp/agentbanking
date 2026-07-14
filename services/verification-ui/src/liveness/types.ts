export type ChallengeType =
  | "TURN_LEFT"
  | "TURN_RIGHT"
  | "BLINK"
  | "NOD"
  | "SMILE";

export type VerificationStatus =
  | "IDLE"
  | "INITIALIZING"
  | "READY"
  | "CHALLENGE"
  | "VERIFYING"
  | "VERIFIED"
  | "REJECTED";

export interface LivenessSignals {
  motion: number;
  challengePassed: boolean;
  timingVariance: number;
  lightVariance: number;
  frameDiff: number;
  score: number;
}

export interface LivenessProof {
  verdict: "VERIFIED" | "REJECTED";
  confidence: number;
  signals: LivenessSignals;
  timestamp: number;
  sessionId: string;
  hash?: string; // Optional for building, required when submitting
}

export interface FrameData {
  imageData: ImageData;
  timestamp: number;
}
