import { KycWorkflowResult } from "../types/workflow";
import { kycVerificationScore } from "../utils/kycVerificationScore";

/**
 * Takes in a kyc verification result struct, and returns a verification score
 * @param verificationResult The result of the verification workflow
 * @returns
 */
export async function calculateKycVerificationScore(verificationResult: KycWorkflowResult) {
  return kycVerificationScore(verificationResult);
}
