import httpStatus from "http-status";
import { tenantRepository } from "../../repositories/tenantRepository";
import { asyncHandler } from "../../middlewares/async";

export const getTenant = asyncHandler(async (req, res) => {
  const tenant = await tenantRepository.findOne(req.params.tenant_id);

  if (tenant && req.headers["x-system-call"] != "true") {
    delete tenant.tenant_secret;
  }

  return res.status(httpStatus.OK).json({
    message: "success",
    tenant,
  });
});
