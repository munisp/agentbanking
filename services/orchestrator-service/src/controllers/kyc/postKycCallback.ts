import { uuid4 } from "@temporalio/workflow";
import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { workflowRunner } from "../../utils/workflowRunner";
import { validateRequest } from "../../validations";
import { KycCustomerCallbackSchema } from "../../validations/schemas";
import { completeAgentOnboardingWorkflow } from "../../workflows/completeAgentOnboardingWorkflow";
import { completeCustomerOnboardingWorkflow } from "../../workflows/completeCustomerOnboardingWorkflow";

export const postKycCallback = asyncHandler(async (req, res) => {
  const payload = validateRequest(KycCustomerCallbackSchema, req.body);

  // Validate Verification score against threshold

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
