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

export const process_verification_event_signal = defineSignal<
  [z.infer<typeof PostVerifyKycValidationSchema>]
>("process_verification_event_signal");

export const terminate_verification_workflow_signal = defineSignal<[boolean]>(
  "terminate_verification_workflow_signal",
);

export async function kycWorkflow(
  args: KycWorkflowArgs,
): Promise<KycWorkflowResult | void> {
  const {
    getAppConfig,
    initShieldKycVerification,
    shieldVerifyFace,
    shieldVerifyData,
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
    let process_verification_event_signal_payload: z.infer<
      typeof PostVerifyKycValidationSchema
    > | null = null;
    let terminate_workflow = false;
    let has_sent_webhook = false;

    // 01. Retreive app config.
    const config = (await getAppConfig("kyc-config")) as any;

    // 02. Init a verification workflow for the user.
    await initShieldKycVerification({
      clientId: config.client_id,
      callbackUrl: config.callback_url,
      redirectUrl: config.redirect_url,
      state,
      userId: args.UIN,
    });

    // Signal Handlers
    setHandler(process_verification_event_signal, (payload) => {
      process_verification_event_signal_payload = payload;
    });

    setHandler(terminate_verification_workflow_signal, (shouldTerminate) => {
      terminate_workflow = shouldTerminate;
    });

    await condition(
      () =>
        Boolean(terminate_workflow) ||
        Boolean(process_verification_event_signal_payload),
    );
    if (terminate_workflow) CancellationScope.current().cancel();

    if (process_verification_event_signal_payload) {
      const faceVerificationResult = await shieldVerifyFace({
        ...(process_verification_event_signal_payload as z.infer<
          typeof PostVerifyKycValidationSchema
        >),
        ...args,
      });

      // 04. Verify data with kyc service.
      const dataVerificationResult = await shieldVerifyData(args, faceVerificationResult.ninData);

      // 05. Calculate verification score.

      const result: KycWorkflowResult = {
        id: args.id,
        faceVerificationResult,
        dataVerificationResult,
        documentVerificationResult: null,
      };
      // 06. Send webhook if configured and not already sent.
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
    console.error("Caught unknown error in shield kyc workflow: ", error);
    await CancellationScope.nonCancellable(
      async () =>
        await endKycVerificationWorkflow(
          args.UIN,
          VerificationWorkflowStatus.FAILED,
        ),
    );
  }
}
