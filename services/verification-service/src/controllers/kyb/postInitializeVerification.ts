import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { validateRequest } from "../../validations";
import { PostInitializeVerificationValidationSchema } from "../../validations/schemas";
import { AuthRequest } from "../../types";
import { workflowRunner } from "../../utils/workflowRunner";
import { KybWorkflowArgs, kybWorkflow, KybWorkflowResult } from "../../workflows/kybWorkflow";
import { uuid4 } from "@temporalio/workflow";

export const postInitializeVerification = asyncHandler(async (req: AuthRequest, res) => {
  const payload = validateRequest(PostInitializeVerificationValidationSchema, req.body);

  const client = req.client!;

  const result = await workflowRunner<KybWorkflowArgs, KybWorkflowResult>(kybWorkflow, {
    args: {
      payload,
      client,
    },
    workflowId: `init-kyb-${uuid4()}`,
    defaultErrorMessage: "Failed to initialize verification workflow.",
  });

  return res.status(httpStatus.CREATED).json(result);
});
