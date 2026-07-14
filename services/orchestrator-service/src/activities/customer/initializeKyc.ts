import { verificationService } from "../../services/verificationService";
import { IKycVerificationPayload, IKycVerificationResponse } from "../../types/verification";

export async function initializeKyc(payload: IKycVerificationPayload): Promise<IKycVerificationResponse> {
  return verificationService.initializeKycVerification(payload);
}
