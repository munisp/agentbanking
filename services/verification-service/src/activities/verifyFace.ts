import * as z from "zod";
import { shieldApiClient } from "../lib/ShieldApiClient";
import { NonRetriableApplicationError } from "../middlewares/error";
import { IVerifyFaceResult } from "../types/verification";
import { KycWorkflowArgs } from "../types/workflow";
import { PostVerifyKycValidationSchema } from "../validations/schemas";

/**
 * Send base64 face to shield to verify against nin passport.
 * @returns
 */
export async function verifyFace(
  payload: z.infer<typeof PostVerifyKycValidationSchema> & KycWorkflowArgs,
): Promise<IVerifyFaceResult> {
  // get face from payload
  const faceImageBase64 = payload.documents?.find(
    (document) => document.type == "face",
  )?.pages?.[0]?.base64;

  // this ends the workflow, allow user re-submit face??
  if (!faceImageBase64) throw new NonRetriableApplicationError("Invalid face.");

  return await shieldApiClient.verifyFace({
    base64Image: faceImageBase64,
    nin: payload.UIN,
  });
}
