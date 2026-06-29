import {
  CancellationScope,
  condition,
  defineSignal,
  proxyActivities,
  setHandler,
} from "@temporalio/workflow";
import * as z from "zod";
import * as activities from "../activities";
import { KycWorkflowArgs, KycWorkflowResult } from "../types/workflow";
import { VerificationWorkflowStatus } from "../utils/enums";
import { PostVerifyKycValidationSchema } from "../validations/schemas";

export const process_default_verification_event_signal = defineSignal<
  [z.infer<typeof PostVerifyKycValidationSchema>]
>("process_default_verification_event_signal");

export const terminate_default_verification_workflow_signal = defineSignal<
  [boolean]
>("terminate_default_verification_workflow_signal");

export async function defaultKycWorkflow(
  args: KycWorkflowArgs,
): Promise<KycWorkflowResult | void> {
  const {
    defaultVerifyFace,
    defaultVerifyData,
    endKycVerificationWorkflow,
    calculateKycVerificationScore,
    sendWebhook,
  } = proxyActivities<typeof activities>({
    retry: {
      initialInterval: "1s",
      maximumAttempts: 3,
      nonRetryableErrorTypes: ["NonRetriableApplicationError"],
    },
    startToCloseTimeout: "1m",
  });

  try {
    const state = `newwave_verify_nin_${args.UIN}`;
    let process_default_verification_event_signal_payload: z.infer<
      typeof PostVerifyKycValidationSchema
    > | null = null;
    let terminate_workflow = false;
    let has_sent_webhook = false;

    setHandler(process_default_verification_event_signal, (input) => {
      process_default_verification_event_signal_payload = input;
    });

    setHandler(terminate_default_verification_workflow_signal, (input) => {
      terminate_workflow = input;
    });

    // keep waiting for a condition to be fulfilled..
    await condition(
      () =>
        Boolean(terminate_workflow) ||
        Boolean(process_default_verification_event_signal_payload),
    );

    if (terminate_workflow) CancellationScope.current().cancel();

    if (process_default_verification_event_signal_payload) {
      // 03. Verify face.
      const faceVerificationResult = await defaultVerifyFace({
        ...(process_default_verification_event_signal_payload as z.infer<
          typeof PostVerifyKycValidationSchema
        >),
        ...args,
      });

      // 04. Verify user data.
      const dataVerificationResult = await defaultVerifyData(
        args,
        faceVerificationResult.ninData,
      );

      // 05(todo). Verify document (should make use of ocr and text similarity tools)

      const result: KycWorkflowResult = {
        id: args.id,
        faceVerificationResult,
        dataVerificationResult,
        documentVerificationResult: null,
        metadata: args.metadata,
      };

      // 06. Calculate verification score.
      result.score = await calculateKycVerificationScore(result);

      // 07. send notification webhook to the client.
      if (args.callBackUrl) {
        has_sent_webhook = await sendWebhook(args.callBackUrl, result);
      }

      // 08. end workflow
      await endKycVerificationWorkflow(
        args.UIN,
        VerificationWorkflowStatus.COMPLETED,
        result.score,
        has_sent_webhook,
      );

      return result;
    }
  } catch (error: unknown) {
    console.error("Caught unknown error in default kyc workflow: ", error);

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
