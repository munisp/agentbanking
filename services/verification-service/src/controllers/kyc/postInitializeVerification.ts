import httpStatus from "http-status";
import logger from "../../config/logger.config";
import { readEnv } from "../../config/readEnv.config";
import { AppDataSource } from "../../database/dataSource";
import { KycVerificationWorkflowEntity } from "../../entity/KycVerificationWorkflowEntity";
import { asyncHandler } from "../../middlewares/async";
import { ApiError } from "../../middlewares/error";
import { setupTemporalClient } from "../../setup/setupTemporalClient";
import { KycWorkflowArgs, KycWorkflowResult } from "../../types/workflow";
import {
  KycIdentityProviders,
  VerificationWorkflowStatus,
} from "../../utils/enums";
import { isKycSimulationMode } from "../../utils/kycSimulationMode";
import { workflowRunner } from "../../utils/workflowRunner";
import { validateRequest } from "../../validations";
import { PostInitializeKycVerificationValidationSchema } from "../../validations/schemas";
import {
  defaultKycWorkflow,
  terminate_default_verification_workflow_signal,
} from "../../workflows/defaultKycWorkflow";
import {
  shieldKycWorkflow,
  terminate_shield_verification_workflow_signal,
} from "../../workflows/shieldKycWorkflow";
import {
  livenessKycWorkflow,
  terminate_liveness_verification_workflow_signal,
} from "../../workflows/livenessKycWorkflow";

// Simulated verification pipelines with no real provider behind them. They
// are only allowed when KYC simulation mode is enabled (non-production).
const SIMULATION_ONLY_PROVIDERS = [
  KycIdentityProviders.DEFAULT,
  KycIdentityProviders.LIVENESS,
];

export const postInitializeVerification = asyncHandler(async (req, res) => {
  const payload = validateRequest(
    PostInitializeKycVerificationValidationSchema,
    req.body,
  );

  const client = req.client!;

  // Fail closed: never silently default to a simulated identity provider.
  // Outside KYC simulation mode the client must explicitly request a real
  // provider (e.g. SHIELD); simulated providers are rejected outright.
  const identityProvider =
    payload.identityProvider ||
    (isKycSimulationMode() ? KycIdentityProviders.LIVENESS : undefined);

  if (!identityProvider) {
    throw new ApiError(
      httpStatus.BAD_REQUEST,
      "identityProvider is required: default identity providers are disabled outside KYC simulation mode.",
      "VER-400-02",
      "verification-service",
    );
  }

  if (
    SIMULATION_ONLY_PROVIDERS.includes(identityProvider) &&
    !isKycSimulationMode()
  ) {
    throw new ApiError(
      httpStatus.SERVICE_UNAVAILABLE,
      `Identity provider '${identityProvider}' is a simulated provider and is not available in this environment. Use a real provider (e.g. '${KycIdentityProviders.SHIELD}').`,
      "VER-503-02",
      "verification-service",
    );
  }

  // Check if existing verification workflow exists and end it.
  const existingKycVerification = await AppDataSource.manager.findOne(
    KycVerificationWorkflowEntity,
    {
      where: {
        client_app_user_id: payload.user.UIN,
        client_id: client.id,
      },
    },
  );

  if (existingKycVerification) {
    // terminate workflow if still in running state
    if (existingKycVerification.status == VerificationWorkflowStatus.RUNNING) {
      try {
        const wfClient = await setupTemporalClient();

        const handle = wfClient!.getHandle(
          `init-${existingKycVerification.identity_provider}-kyc-${existingKycVerification.id}`,
        );

        // Check if workflow actually exists before trying to signal it
        try {
          await handle.describe();
          
          // send terminate signal to workflow only if it exists
          if (
            existingKycVerification.identity_provider ===
            KycIdentityProviders.SHIELD
          ) {
            await handle.signal(
              terminate_shield_verification_workflow_signal,
              true,
            );
          } else if (
            existingKycVerification.identity_provider ===
            KycIdentityProviders.DEFAULT
          ) {
            await handle.signal(
              terminate_default_verification_workflow_signal,
              true,
            );
          } else if (
            existingKycVerification.identity_provider ===
            KycIdentityProviders.LIVENESS
          ) {
            await handle.signal(
              terminate_liveness_verification_workflow_signal,
              true,
            );
          }
        } catch (describeError: any) {
          // Workflow doesn't exist in Temporal, just log and continue
          logger.warn(
            `Workflow init-${existingKycVerification.identity_provider}-kyc-${existingKycVerification.id} not found in Temporal, skipping termination signal`,
          );
        }
      } catch (clientError: any) {
        // Failed to get Temporal client, log but continue
        logger.error(`Failed to get Temporal client for workflow termination:`, clientError.message);
      }
    }

    // delete database entry
    await AppDataSource.manager.remove(existingKycVerification);
  }

  const kycVerification = new KycVerificationWorkflowEntity();

  kycVerification.identity_provider = identityProvider;
  kycVerification.client = client;
  kycVerification.client_app_user_id = payload.user.UIN;

  try {
    await AppDataSource.manager.save(kycVerification);
  } catch (dbError: any) {
    throw new ApiError(
      httpStatus.INTERNAL_SERVER_ERROR,
      `Failed to save KYC verification record: ${dbError.message}`,
      "VER-500-01",
      "verification-service",
    );
  }

  const url = `${readEnv("KYC_FLOW_BASE_URL")}?verification_id=${kycVerification.id}&identity_provider=${
    kycVerification.identity_provider
  }${payload.redirectUrl ? "&redirect_url=" + payload.redirectUrl : ""}${
    payload.metadata ? `&metadata=${encodeURIComponent(JSON.stringify(payload.metadata))}` : ""
  }`;

  try {
    if (identityProvider == KycIdentityProviders.SHIELD) {
      await workflowRunner<KycWorkflowArgs, KycWorkflowResult | void>(
        shieldKycWorkflow,
        {
          args: {
            id: kycVerification.id,
            callBackUrl: client.callback_url || undefined,
            ...payload.user,
            metadata: payload.metadata || undefined,
          },
          workflowId: `init-shield-kyc-${kycVerification.id}`,
          defaultErrorMessage:
            "Failed to initialize shield kyc verification workflow.",
          isDaemon: true,
        },
      );
    } else if (identityProvider == KycIdentityProviders.DEFAULT) {
      await workflowRunner<KycWorkflowArgs, KycWorkflowResult | void>(
        defaultKycWorkflow,
        {
          args: {
            id: kycVerification.id,
            callBackUrl: client.callback_url || undefined,
            ...payload.user,
            metadata: payload.metadata || undefined,
          },
          workflowId: `init-default-kyc-${kycVerification.id}`,
          defaultErrorMessage:
            "Failed to initialize default kyc verification workflow.",
          isDaemon: true,
        },
      );
    } else if (identityProvider == KycIdentityProviders.LIVENESS) {
      await workflowRunner<KycWorkflowArgs, KycWorkflowResult | void>(
        livenessKycWorkflow,
        {
          args: {
            id: kycVerification.id,
            callBackUrl: client.callback_url || undefined,
            ...payload.user,
            metadata: payload.metadata || undefined,
          },
          workflowId: `init-liveness-kyc-${kycVerification.id}`,
          defaultErrorMessage:
            "Failed to initialize liveness kyc verification workflow.",
          isDaemon: true,
        },
      );
    } else {
      throw new ApiError(
        httpStatus.NOT_IMPLEMENTED,
        "Not supported.",
        "VER-501-00",
        "verification-service",
      );
    }
  } catch (workflowError: any) {
    // Clean up the database record if workflow initialization fails
    await AppDataSource.manager.remove(kycVerification);
    throw workflowError;
  }

  return res.status(httpStatus.CREATED).json({
    id: kycVerification.id,
    url,
  });
});
