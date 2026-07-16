import { uuid4 } from "@temporalio/workflow";
import { asyncHandler } from "../../middlewares/async";
import { workflowRunner } from "../../utils/workflowRunner";
import { validateRequest } from "../../validations";
import httpStatus from "http-status";
import { tenantService } from "../../services/tenantService";
import { CreateAdminSchema } from "../../validations/schemas";
import { ApiError } from "../../middlewares/error";
import { createAdminWorkflow } from "../../workflows/createAdminWorkflow";

export const postCreateAdmin = asyncHandler(async (req, res) => {
  const payload = validateRequest(CreateAdminSchema, req.body);

  const tenantId = req.headers["x-tenant-id"] as string;
  const keycloakRealm = "54agent_" + tenantId;
  const keycloakPublicKey = await tenantService.getKeycloakPublicKey(tenantId);

  if (!tenantId) throw new ApiError(httpStatus.BAD_REQUEST, "Tenant ID is required.");

  const verification = await workflowRunner(createAdminWorkflow, {
    args: { ...payload, tenantId, keycloakRealm, keycloakPublicKey },
    workflowId: `54agent_create_tenant_admin_${tenantId}_${uuid4()}`,
    defaultErrorMessage: "Tenant admin creation failed.",
    withTimeOut: 40000,
    timeOutFn: () => {
      return res.status(httpStatus.ACCEPTED).json({
        isSuccessful: true,
        message: "Tenant admin creation processing... You’ll be notified when it’s done.",
        responseModel: {},
      });
    },
  });

  console.log("workflow response", verification);

  return res.status(httpStatus.CREATED).json({ message: "success", verification });
});
