import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { tenantRepository } from "../../repositories/tenantRepository";

export const getTenantFeatures = asyncHandler(async (req, res) => {
  const tenantId = req.headers["x-tenant-id"] as string;

  return res.status(httpStatus.OK).json({
    features: await tenantRepository.getFeatures(tenantId),
  });
});
