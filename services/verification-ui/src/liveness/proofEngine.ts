/**
 * Proof Engine
 * Builds cryptographic proof of liveness verification
 */

import type { LivenessProof, LivenessSignals } from "./types";

export function buildProof(
  signals: LivenessSignals,
  verdict: "VERIFIED" | "REJECTED",
): LivenessProof {
  return {
    verdict,
    confidence: signals.score,
    signals,
    timestamp: Date.now(),
    sessionId: crypto.randomUUID(),
  };
}

export function serializeProof(proof: LivenessProof): string {
  return JSON.stringify(proof, null, 2);
}

export function hashProof(proof: LivenessProof): Promise<string> {
  const data = JSON.stringify(proof);
  const encoder = new TextEncoder();
  const dataBuffer = encoder.encode(data);

  return crypto.subtle.digest("SHA-256", dataBuffer).then((hashBuffer) => {
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");
  });
}

export async function sendProofToServer(
  proof: LivenessProof,
  endpoint: string = "/api/verify",
): Promise<Response> {
  const proofHash = await hashProof(proof);

  return fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ...proof,
      proofHash,
    }),
  });
}

export function validateProofStructure(proof: unknown): proof is LivenessProof {
  if (typeof proof !== "object" || proof === null) {
    return false;
  }

  const p = proof as Record<string, unknown>;

  return (
    (p.verdict === "VERIFIED" || p.verdict === "REJECTED") &&
    typeof p.confidence === "number" &&
    typeof p.signals === "object" &&
    typeof p.timestamp === "number" &&
    typeof p.sessionId === "string"
  );
}

export function generateProofReport(proof: LivenessProof): string {
  const { verdict, confidence, signals, timestamp, sessionId } = proof;

  return `
╔═══════════════════════════════════════╗
║     LIVENESS VERIFICATION REPORT      ║
╚═══════════════════════════════════════╝

Session ID: ${sessionId}
Timestamp: ${new Date(timestamp).toISOString()}

VERDICT: ${verdict}
Confidence: ${(confidence * 100).toFixed(1)}%

═══════════════════════════════════════

SIGNAL ANALYSIS:
  • Motion Score: ${(signals.motion * 100).toFixed(1)}%
  • Challenge: ${signals.challengePassed ? "✓ PASSED" : "✗ FAILED"}
  • Timing Variance: ${(signals.timingVariance * 100).toFixed(1)}%
  • Light Variance: ${(signals.lightVariance * 100).toFixed(1)}%
  • Frame Difference: ${(signals.frameDiff * 100).toFixed(1)}%

═══════════════════════════════════════
  `.trim();
}
