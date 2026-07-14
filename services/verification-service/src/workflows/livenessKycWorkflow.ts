import {
  CancellationScope,
  condition,
  defineSignal,
  proxyActivities,
  setHandler,
} from "@temporalio/workflow";
import * as z from "zod";
import type * as activities from "../activities";
import { KycWorkflowArgs, KycWorkflowResult } from "../types/workflow";
import { VerificationWorkflowStatus } from "../utils/enums";
import { PostVerifyKycValidationSchema } from "../validations/schemas";

export const process_liveness_verification_event_signal = defineSignal<
  [z.infer<typeof PostVerifyKycValidationSchema>]
>("process_liveness_verification_event_signal");

export const terminate_liveness_verification_workflow_signal = defineSignal<
  [boolean]
>("terminate_liveness_verification_workflow_signal");

/**
 * Liveness-based KYC Workflow
 * Uses liveness detection instead of Shield/Ballerine for KYC verification
 */
export async function livenessKycWorkflow(
  args: KycWorkflowArgs,
): Promise<KycWorkflowResult | void> {
  const {
    defaultVerifyFace,
    defaultVerifyData,
    verifyDocument,
    endKycVerificationWorkflow,
    calculateKycVerificationScore,
    sendWebhook,
  } = proxyActivities<typeof activities>({
    retry: {
      initialInterval: "1s",
      maximumAttempts: 3,
      nonRetryableErrorTypes: ["NonRetriableApplicationError"],
    },
    startToCloseTimeout: "2m",
  });

  // Direct import workaround for validateLivenessProof TypeScript issue
  const validateLivenessProof = proxyActivities<
    typeof import("../activities/validateLivenessProof")
  >({
    retry: {
      initialInterval: "1s",
      maximumAttempts: 3,
      nonRetryableErrorTypes: ["NonRetriableApplicationError"],
    },
    startToCloseTimeout: "2m",
  }).validateLivenessProof;

  try {
    let process_liveness_verification_event_signal_payload: z.infer<
      typeof PostVerifyKycValidationSchema
    > | null = null;
    let terminate_workflow = false;
    let has_sent_webhook = false;

    setHandler(process_liveness_verification_event_signal, (input) => {
      process_liveness_verification_event_signal_payload = input;
    });

    setHandler(terminate_liveness_verification_workflow_signal, (input) => {
      terminate_workflow = input;
    });

    // Wait for verification data from UI
    await condition(
      () =>
        Boolean(terminate_workflow) ||
        Boolean(process_liveness_verification_event_signal_payload),
    );

    if (terminate_workflow) CancellationScope.current().cancel();

    if (process_liveness_verification_event_signal_payload) {
      const payload: z.infer<typeof PostVerifyKycValidationSchema> =
        process_liveness_verification_event_signal_payload;

      // 01. Validate liveness proof
      const livenessResult = await validateLivenessProof({
        livenessProof: payload.livenessProof!,
        sessionId: payload.endUserInfo.id,
      });

      if (!livenessResult.isValid) {
        throw new Error(
          "Liveness verification failed: " + livenessResult.reason,
        );
      }

      // 02. Verify document authenticity and extract data (optional)
      let documentVerificationResult = null;
      let extractedUserData = {
        nin: args.UIN,
        firstName: args.firstName || "",
        lastName: args.lastName || "",
        dateOfBirth: args.dateOfBirth || "",
        phone: args.phone,
      };

      if (payload.document?.frontImage && payload.document?.backImage) {
        documentVerificationResult = await verifyDocument({
          frontImage: payload.document.frontImage,
          backImage: payload.document.backImage,
          documentType: payload.document.type,
          country: payload.document.country,
        });

        // Map extracted data to expected format
        extractedUserData = {
          nin:
            documentVerificationResult.extractedData.documentNumber || args.UIN,
          firstName:
            documentVerificationResult.extractedData.firstName ||
            args.firstName ||
            "",
          lastName:
            documentVerificationResult.extractedData.lastName ||
            args.lastName ||
            "",
          dateOfBirth:
            documentVerificationResult.extractedData.dateOfBirth ||
            args.dateOfBirth ||
            "",
          phone: args.phone,
        };
      }

      // 03. Verify face from selfie against document
      // Create a compatible payload for defaultVerifyFace
      const faceVerificationPayload: any = {
        ...args,
        documents: [
          {
            type: "face" as const,
            pages: [{ base64: payload.selfie!.image }],
          },
        ],
      };
      const faceVerificationResult = await defaultVerifyFace(
        faceVerificationPayload,
      );

      // 04. Verify extracted data against user-provided data
      const dataVerificationResult = await defaultVerifyData(
        args,
        extractedUserData,
      );

      const result: KycWorkflowResult = {
        id: args.id,
        faceVerificationResult,
        dataVerificationResult,
        documentVerificationResult,
        metadata: args.metadata,
      };

      // 05. Calculate verification score
      result.score = await calculateKycVerificationScore(result);

      // 06. Send notification webhook to the client
      if (args.callBackUrl) {
        has_sent_webhook = await sendWebhook(args.callBackUrl, result);
      }

      // 07. End workflow
      await endKycVerificationWorkflow(
        args.UIN,
        VerificationWorkflowStatus.COMPLETED,
        result.score,
        has_sent_webhook,
      );

      return result;
    }
  } catch (error: unknown) {
    console.error("Caught unknown error in liveness kyc workflow: ", error);

    // Send failure webhook to notify the orchestrator
    if (args.callBackUrl) {
      try {
        const failureResult: KycWorkflowResult = {
          id: args.id,
          faceVerificationResult: {
            success: false,
            similarity: 0,
            ninData: {
              nin: "",
              firstName: "",
              lastName: "",
              dateOfBirth: "",
              phone: "",
            },
          },
          dataVerificationResult: {
            firstName: false,
            lastName: false,
            dateOfBirth: false,
            phone: false,
            UIN: false,
          },
          documentVerificationResult: null,
          metadata: args.metadata,
          score: 0,
        };
        await sendWebhook(args.callBackUrl, failureResult);
      } catch (webhookError) {
        console.error("Failed to send failure webhook:", webhookError);
      }
    }

    await CancellationScope.nonCancellable(
      async () =>
        await endKycVerificationWorkflow(
          args.UIN,
          VerificationWorkflowStatus.FAILED,
        ),
    );
  }
}
