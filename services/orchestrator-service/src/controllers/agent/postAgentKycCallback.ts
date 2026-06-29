import { uuid4 } from "@temporalio/workflow";
import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { workflowRunner } from "../../utils/workflowRunner";
import { validateRequest } from "../../validations";
import { KycAgentCallbackSchema } from "../../validations/schemas";
import { completeAgentOnboardingWorkflow } from "../../workflows/completeAgentOnboardingWorkflow";

export const postAgentKycCallback = asyncHandler(async (req, res) => {
  const payload = validateRequest(KycAgentCallbackSchema, req.body);

  // Validate Verification score against threshold

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

  return res.status(httpStatus.OK).json({ message: "success" });
});
