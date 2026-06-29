/**
 * Liveness Detection Engine
 * Main export file for all liveness modules
 */

// Types
export type {
    ChallengeType, FrameData, LivenessProof, LivenessSignals, VerificationStatus
} from "./types";

// Camera
export { initCamera, isCameraAvailable, stopCamera } from "./camera";

// Frame Engine
export {
    addToBuffer, captureFrame,
    createFrameBuffer, getAverageFrameData
} from "./frameEngine";

// Motion Engine
export {  isMoving, motionScore } from "./motionEngine";

// Frame Diff Engine
export {
    detectReplayPattern, frameDiff, isStaticImage
} from "./frameDiffEngine";

// Light Engine
export {
    detectScreenFlicker,
    getAverageBrightness, lightVariance
} from "./lightEngine";

// Challenge Engine
export {
    CHALLENGES,
    CHALLENGE_INSTRUCTIONS,
    generateChallenge,
    generateChallengeSequence,
    getChallengeInstruction,
    verifyChallengeResponse
} from "./challengeEngine";

// Timing Engine
export {
    analyzeTimingPattern, calculateResponseTime, isTimingNatural, timingVariance
} from "./timingEngine";

// Scoring Engine
export { analyzeSignals, getVerdict, scoreEngine } from "./scoringEngine";
export type { SignalInputs } from "./scoringEngine";

// Proof Engine
export {
    buildProof, generateProofReport, hashProof,
    sendProofToServer, serializeProof, validateProofStructure
} from "./proofEngine";

