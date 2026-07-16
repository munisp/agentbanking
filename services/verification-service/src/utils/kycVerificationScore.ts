import { KycWorkflowResult } from "../types/workflow";

/**
 * Takes in a kyc verification result struct, and returns a verification score
 * @param verificationResult The result of the verification workflow
 * @returns
 */
export function kycVerificationScore(verificationResult: KycWorkflowResult) {
  let faceVerificationScore = (verificationResult.faceVerificationResult?.similarity || 0) * 0.42;

  let dataVerificationScore = 0;

  for (const key of ["UIN", "firstName", "lastName"] as const) {
    if (!verificationResult.dataVerificationResult?.[key]) {
      return 0;
    }
  }

  if (verificationResult.dataVerificationResult?.phone) dataVerificationScore += 0.08;
  if (verificationResult.dataVerificationResult?.dateOfBirth) dataVerificationScore += 0.08;

  let documentVerificationScore = (verificationResult.documentVerificationResult?.similarity || 0) * 0.42;

  return Number((faceVerificationScore + dataVerificationScore + documentVerificationScore).toFixed(3));
}
