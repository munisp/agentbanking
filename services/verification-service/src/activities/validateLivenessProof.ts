/**
 * Validate liveness proof from UI
 */
export async function validateLivenessProof(args: {
  livenessProof: {
    sessionId: string;
    timestamp: number;
    confidence: number;
    verdict: string;
    signals: {
      motion: number;
      challengePassed: boolean;
      timingVariance: number;
      lightVariance: number;
      frameDiff: number;
    };
    hash: string;
  };
  sessionId: string;
}): Promise<{ isValid: boolean; reason?: string }> {
  try {
    // Validate basic proof structure
    if (!args.livenessProof || !args.livenessProof.sessionId) {
      return { isValid: false, reason: "Invalid proof structure" };
    }

    // Note: We don't validate sessionId match because the liveness proof generates
    // its own session ID on the frontend, which is different from the verification ID

    // Check verdict
    if (args.livenessProof.verdict !== "VERIFIED") {
      return { isValid: false, reason: "Liveness check was not verified" };
    }

    // Validate confidence threshold (80% minimum)
    if (args.livenessProof.confidence < 0.8) {
      return { isValid: false, reason: "Confidence score too low" };
    }

    // Validate motion detection
    if (args.livenessProof.signals.motion < 0.2) {
      return { isValid: false, reason: "Insufficient motion detected" };
    }

    // Validate challenge response
    if (!args.livenessProof.signals.challengePassed) {
      return { isValid: false, reason: "Challenge not passed" };
    }

    // Check timestamp (not older than 5 minutes)
    const fiveMinutesAgo = Date.now() - 5 * 60 * 1000;
    if (args.livenessProof.timestamp < fiveMinutesAgo) {
      return { isValid: false, reason: "Proof expired" };
    }

    return { isValid: true };
  } catch (error) {
    console.error("Error validating liveness proof:", error);
    return { isValid: false, reason: "Validation error: " + (error as Error).message };
  }
}
