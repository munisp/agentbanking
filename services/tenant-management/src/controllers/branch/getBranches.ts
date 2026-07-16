import httpStatus from "http-status";
import { tenantRepository } from "../../repositories/tenantRepository";
import { asyncHandler } from "../../middlewares/async";

export const getBranches = asyncHandler(async (req, res) => {
  const tenantId = req.headers["x-tenant-id"] as string;

  const branches = await tenantRepository.getBranches(tenantId);

  return res.status(httpStatus.OK).json({
    status: "success",
    branches,
  });
});
