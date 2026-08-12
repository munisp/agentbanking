import * as z from "zod";
import { PostVerifyKycValidationSchema } from "../validations/schemas";
import { KycWorkflowArgs } from "../types/workflow";
import { NonRetriableApplicationError } from "../middlewares/error";
import { IVerifyFaceResult } from "../types/verification";
import { assertKycSimulationMode } from "../utils/kycSimulationMode";

/**
 * Send base64 face to verify against.
 *
 * SIMULATION ONLY: this activity does not call any real biometric provider.
 * It is hard-gated behind KYC simulation mode and must never run in
 * production.
 * @returns
 */
export async function defaultVerifyFace(
  payload: z.infer<typeof PostVerifyKycValidationSchema> & KycWorkflowArgs
): Promise<IVerifyFaceResult> {
  // Fail closed: never return a fabricated face-match outside simulation mode.
  assertKycSimulationMode("defaultVerifyFace");

  // get face from payload
  const faceImageBase64 = payload.documents?.find((document) => document.type == "face")?.pages?.[0]?.base64;

  // this ends the workflow, allow user re-submit face??
  if (!faceImageBase64) throw new NonRetriableApplicationError("Invalid face.");

  return {
    success: true,
    similarity: 1,
    ninData: {
      nin: payload.UIN,
      firstName: payload.firstName || "",
      lastName: payload.lastName,
      dateOfBirth: payload.dateOfBirth || "",
      phone: payload.phone,
    },
  };
}
