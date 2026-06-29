import httpStatus from "http-status";
import { AppDataSource } from "../../database/dataSource";
import { KycVerificationWorkflowEntity } from "../../entity/KycVerificationWorkflowEntity";
import { asyncHandler } from "../../middlewares/async";
import { ApiError } from "../../middlewares/error";
import { setupTemporalClient } from "../../setup/setupTemporalClient";
import { KycIdentityProviders } from "../../utils/enums";
import { validateRequest } from "../../validations";
import { PostVerifyKycValidationSchema } from "../../validations/schemas";
import {
  process_default_verification_event_signal,
  process_shield_verification_event_signal,
} from "../../workflows";
import { process_liveness_verification_event_signal } from "../../workflows/livenessKycWorkflow";

export const postVerify = asyncHandler(async (req, res) => {
  const payload = validateRequest(PostVerifyKycValidationSchema, req.body);

  const kycVerification = await AppDataSource.manager.findOne(
    KycVerificationWorkflowEntity,
    {
      where: {
        id: payload.endUserInfo.id,
      },
    },
  );

  if (!kycVerification)
    throw new ApiError(
      httpStatus.BAD_REQUEST,
      "Invalid verification session.",
      "VER-400-00",
      "verification-service",
    );

  // send signal to running wf with new data..
  const wfClient = await setupTemporalClient();

  const handle = wfClient!.getHandle(
    `init-${kycVerification.identity_provider}-kyc-${kycVerification.id}`,
  );

  // send process verification signal to running workflow
  if (kycVerification.identity_provider === KycIdentityProviders.SHIELD) {
    await handle.signal(process_shield_verification_event_signal, payload);
  } else if (
    kycVerification.identity_provider === KycIdentityProviders.DEFAULT
  ) {
    await handle.signal(process_default_verification_event_signal, payload);
  } else if (
    kycVerification.identity_provider === KycIdentityProviders.LIVENESS
  ) {
    await handle.signal(process_liveness_verification_event_signal, payload);
  }

  // can await result here?
  const result = await handle.result();

  return res.status(httpStatus.OK).json(result);
});
