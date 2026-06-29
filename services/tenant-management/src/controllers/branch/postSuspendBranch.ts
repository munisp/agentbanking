import { asyncHandler } from "../../middlewares/async";
import { tenantRepository } from "../../repositories/tenantRepository";

export const postSuspendBranch = asyncHandler(async (req, res) => {
  const branchId = req.params.branch_id;
  const tenantId = req.params.tenant_id;

  await tenantRepository.suspendBranch(tenantId, parseInt(branchId));

  return res.status(200).json({ message: "Branch suspended successfully" });
});
