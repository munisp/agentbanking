import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { tenantRepository } from "../../repositories/tenantRepository";
import { PutUpdateBranchSchema, validateRequest } from "../../validations";

export const putUpdateBranch = asyncHandler(async (req, res) => {
  const payload = validateRequest(PutUpdateBranchSchema, req.body);

  const tenantId = req.headers["x-tenant-id"] as string;

  const branchId = req.params.branch_id;

  const branch = await tenantRepository.updateBranch(tenantId, parseInt(branchId!), payload);

  return res.status(httpStatus.OK).json({
    status: "success",
    branch,
  });
});
