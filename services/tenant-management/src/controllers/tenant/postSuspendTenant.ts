import { asyncHandler } from "../../middlewares/async";
import { tenantRepository } from "../../repositories/tenantRepository";

export const postSuspendTenant = asyncHandler(async (req, res) => {
  const tenantId = req.params.tenant_id;

  tenantRepository.suspendTenant(tenantId);

  return res.status(200).json({
    message: `Tenant with ID ${tenantId} has been suspended successfully.`,
  });
});
