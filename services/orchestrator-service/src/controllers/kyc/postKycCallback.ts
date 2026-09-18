import crypto from "crypto";
import { uuid4 } from "@temporalio/workflow";
import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { ApiError } from "../../middlewares/error";
import { workflowRunner } from "../../utils/workflowRunner";
import { validateRequest } from "../../validations";
import { KycCustomerCallbackSchema } from "../../validations/schemas";
import { completeAgentOnboardingWorkflow } from "../../workflows/completeAgentOnboardingWorkflow";
import { completeCustomerOnboardingWorkflow } from "../../workflows/completeCustomerOnboardingWorkflow";

const KYC_CALLBACK_SIGNATURE_HEADER = "x-kyc-callback-signature";

/**
 * Verifies the HMAC-SHA256 signature of an inbound KYC callback.
 *
 * The verification provider must send the hex-encoded HMAC-SHA256 of the
 * request body, keyed with the shared KYC_CALLBACK_SECRET, in the
 * `x-kyc-callback-signature` header (an optional `sha256=` prefix is
 * tolerated).
 *
 * NOTE: app.ts registers `express.json()` without a `verify` hook, so the
 * raw request body is not retained and is unavailable here. The signature is
 * therefore computed over `JSON.stringify(req.body)` (the re-serialized
 * parsed body); the caller must sign the identical JSON serialization.
 *
 * Fails closed: if KYC_CALLBACK_SECRET is not configured, every callback is
 * rejected with 503 — unauthenticated callbacks are never allowed.
 */
const verifyKycCallbackSignature = (reqBody: unknown, signatureHeader: unknown): void => {
  const secret = process.env.KYC_CALLBACK_SECRET;
  if (!secret) {
    throw new ApiError(
      httpStatus.SERVICE_UNAVAILABLE,
      "KYC callback secret is not configured; rejecting callback.",
    );
  }

  if (typeof signatureHeader !== "string" || signatureHeader.length === 0) {
    throw new ApiError(httpStatus.UNAUTHORIZED, "Missing KYC callback signature.");
  }

  const expected = crypto
    .createHmac("sha256", secret)
    .update(JSON.stringify(reqBody))
    .digest("hex");
  const provided = signatureHeader.replace(/^sha256=/, "");

  const expectedBuf = Buffer.from(expected, "utf8");
  const providedBuf = Buffer.from(provided, "utf8");
  if (
    expectedBuf.length !== providedBuf.length ||
    !crypto.timingSafeEqual(expectedBuf, providedBuf)
  ) {
    throw new ApiError(httpStatus.UNAUTHORIZED, "Invalid KYC callback signature.");
  }
};

export const postKycCallback = asyncHandler(async (req, res) => {
  // Authenticate the callback before any processing.
  verifyKycCallbackSignature(req.body, req.headers[KYC_CALLBACK_SIGNATURE_HEADER]);

  const payload = validateRequest(KycCustomerCallbackSchema, req.body);

  // Validate Verification score against threshold
  const minScore = Number(process.env.KYC_SCORE_THRESHOLD_MIN || "0.7");
  if (typeof payload.score !== "number" || !(payload.score >= minScore)) {
    throw new ApiError(
      httpStatus.UNPROCESSABLE_ENTITY,
      `Verification score below threshold (min ${minScore}).`,
    );
  }

  // Require a successful face verification. Fail closed when the field is
  // absent from the payload.
  if (!payload.faceVerificationResult || payload.faceVerificationResult.success !== true) {
    throw new ApiError(
      httpStatus.UNPROCESSABLE_ENTITY,
      "Face verification did not succeed.",
    );
  }

  // Check if this is an agent KYC callback
  const isAgent = payload.metadata.is_agent === true;

  if (isAgent) {
    // Route to agent onboarding workflow
    await workflowRunner(completeAgentOnboardingWorkflow, {
      args: payload,
      workflowId: `54agent_complete_agent_onboarding_${payload.metadata.keycloak_id}_${uuid4()}`,
      defaultErrorMessage: "Complete agent onboarding failed.",
      withTimeOut: 40000,
      timeOutFn: () => {
        return res.status(httpStatus.ACCEPTED).json({
          isSuccessful: true,
          message:
            "Complete agent onboarding processing... You'll be notified when it's done.",
          responseModel: {},
        });
      },
    });
  } else {
    // Route to customer onboarding workflow
    await workflowRunner(completeCustomerOnboardingWorkflow, {
      args: payload,
      workflowId: `54agent_complete_customer_onboarding_${payload.metadata.keycloak_id}_${uuid4()}`,
      defaultErrorMessage: "Complete customer onboarding failed.",
      withTimeOut: 40000,
      timeOutFn: () => {
        return res.status(httpStatus.ACCEPTED).json({
          isSuccessful: true,
          message:
            "Complete customer onboarding processing... You'll be notified when it's done.",
          responseModel: {},
        });
      },
    });
  }

  return res.status(httpStatus.OK).json({ message: "success" });
});
