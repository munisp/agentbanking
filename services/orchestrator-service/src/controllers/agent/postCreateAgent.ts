import { uuid4 } from "@temporalio/workflow";
import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { ApiError } from "../../middlewares/error";
import { tenantService } from "../../services/tenantService";
import { workflowRunner } from "../../utils/workflowRunner";
import { validateRequest } from "../../validations";
import { CreateAgentSchema } from "../../validations/schemas";
import { createAgentWorkflow } from "../../workflows/createAgentWorkflow";

export const postCreateAgent = asyncHandler(async (req, res) => {
  const payload = validateRequest(CreateAgentSchema, req.body);

  const tenantId = req.headers["x-tenant-id"] as string;
  const keycloakRealm = "54agent_" + tenantId;
  const keycloakPublicKey = await tenantService.getKeycloakPublicKey(tenantId);

  if (!tenantId)
    throw new ApiError(httpStatus.BAD_REQUEST, "Tenant ID is required.");

  const verification = await workflowRunner(createAgentWorkflow, {
    args: { ...payload, tenantId, keycloakRealm, keycloakPublicKey },
    workflowId: `54agent_create_agent_${tenantId}_${uuid4()}`,
    defaultErrorMessage: "Agent creation failed.",
    withTimeOut: 40000,
    timeOutFn: () => {
      return res.status(httpStatus.ACCEPTED).json({
        isSuccessful: true,
        message:
          "Agent creation processing... You'll be notified when it's done.",
        responseModel: {},
      });
    },
  });

  console.log("workflow response", verification);

  return res
    .status(httpStatus.CREATED)
    .json({ message: "success", verification });
});
