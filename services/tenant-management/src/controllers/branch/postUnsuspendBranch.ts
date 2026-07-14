import { asyncHandler } from "../../middlewares/async";
import { tenantRepository } from "../../repositories/tenantRepository";

export const postUnsuspendBranch = asyncHandler(async (req, res) => {
  const branchId = req.params.branch_id;
  const tenantId = req.params.tenant_id;

  await tenantRepository.unSuspendBranch(tenantId, parseInt(branchId));

  return res.status(200).json({ message: "Branch un-suspended successfully" });
});
