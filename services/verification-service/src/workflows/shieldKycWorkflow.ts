import {
  CancellationScope,
  condition,
  defineSignal,
  proxyActivities,
  setHandler,
} from "@temporalio/workflow";
import * as activities from "../activities";
import { ShieldConfig } from "../types/config";
import { KycWorkflowArgs, KycWorkflowResult } from "../types/workflow";
import * as z from "zod";
import { PostVerifyKycValidationSchema } from "../validations/schemas";
import { VerificationWorkflowStatus } from "../utils/enums";

export const process_shield_verification_event_signal = defineSignal<
  [z.infer<typeof PostVerifyKycValidationSchema>]
>("process_shield_verification_event_signal");

export const terminate_shield_verification_workflow_signal = defineSignal<[boolean]>(
  "terminate_shield_verification_workflow_signal"
);

export async function shieldKycWorkflow(args: KycWorkflowArgs): Promise<KycWorkflowResult | void> {
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
    let process_shield_verification_event_signal_payload: z.infer<
      typeof PostVerifyKycValidationSchema
    > | null = null;
    let terminate_workflow = false;
    let has_sent_webhook = false;

    // 01. Retreive shield app config.
    const config = (await getAppConfig("shield-config")) as ShieldConfig;

    // 02. Init a shield verification workflow for the user.
    await initShieldKycVerification({
      clientId: config.client_id,
      callbackUrl: config.callback_url,
      redirectUrl: config.redirect_url,
      state,
      userId: args.UIN,
    });

    setHandler(process_shield_verification_event_signal, (input) => {
      process_shield_verification_event_signal_payload = input;
    });

    setHandler(terminate_shield_verification_workflow_signal, (input) => {
      terminate_workflow = input;
    });

    // keep waiting for a condition to be fulfilled..
    await condition(
      () => Boolean(terminate_workflow) || Boolean(process_shield_verification_event_signal_payload)
    );

    if (terminate_workflow) CancellationScope.current().cancel();

    if (process_shield_verification_event_signal_payload) {
      // 03. Verify face with shield.
      const faceVerificationResult = await shieldVerifyFace({
        ...(process_shield_verification_event_signal_payload as z.infer<
          typeof PostVerifyKycValidationSchema
        >),
        ...args,
      });

      // 04. Verify user data.
      const dataVerificationResult = await shieldVerifyData(args, faceVerificationResult.ninData);

      // 05(todo). Verify document with shield(should make use of ocr and text similarity tools)

      const result: KycWorkflowResult = {
        id: args.id,
        faceVerificationResult,
        dataVerificationResult,
        documentVerificationResult: null,
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
        has_sent_webhook
      );

      return result;
    }
  } catch (error: unknown) {
    console.error("Caught unknown error in shield kyc workflow: ", error);
    await CancellationScope.nonCancellable(
      async () => await endKycVerificationWorkflow(args.UIN, VerificationWorkflowStatus.FAILED)
    );
  }
}
