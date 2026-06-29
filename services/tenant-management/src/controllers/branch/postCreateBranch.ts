import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { tenantRepository } from "../../repositories/tenantRepository";
import { PostCreateBranchSchema, validateRequest } from "../../validations";

export const postCreateBranch = asyncHandler(async (req, res) => {
  const payload = validateRequest(PostCreateBranchSchema, req.body);

  const tenantId = req.headers["x-tenant-id"] as string;

  const branch = await tenantRepository.createBranch(tenantId, payload);

  return res.status(httpStatus.CREATED).json({
    status: "success",
    branch,
  });
});
