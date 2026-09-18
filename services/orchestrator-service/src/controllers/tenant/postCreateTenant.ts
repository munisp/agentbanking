import { asyncHandler } from "../../middlewares/async";
import { deterministicWorkflowId } from "../../utils/deterministicWorkflowId";
import { workflowRunner } from "../../utils/workflowRunner";
import { validateRequest } from "../../validations";
import { createTenantWorkflow } from "../../workflows/createTenantWorkflow";
import httpStatus from "http-status";
import { generateSlug } from "../../utils";
import { CreateTenantSchema } from "../../validations/schemas";

export const postCreateTenant = asyncHandler(async (req, res) => {
  const payload = validateRequest(CreateTenantSchema, req.body);

  const tenantId = generateSlug(payload.name);

  const ledgerId = "1"; // Default ledger ID for new tenants

  const tenant = await workflowRunner(createTenantWorkflow, {
    args: { ...payload, tenantId, ledgerId },
    // Deterministic workflowId — retries resume the same workflow instead of
    // duplicating tenant provisioning.
    workflowId: deterministicWorkflowId(
      "54agent_create_tenant",
      tenantId,
      "tenant",
      tenantId,
    ),
    defaultErrorMessage: "Tenant creation failed.",
    withTimeOut: 40000,
    timeOutFn: () => {
      return res.status(httpStatus.ACCEPTED).json({
        isSuccessful: true,
        message: "Tenant creation processing... You’ll be notified when it’s done.",
        responseModel: {},
      });
    },
  });

  return res.status(httpStatus.CREATED).json({ message: "success", tenant });
});
