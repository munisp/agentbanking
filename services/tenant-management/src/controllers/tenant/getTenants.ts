import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { tenantRepository } from "../../repositories/tenantRepository";

export const getTenants = asyncHandler(async (req, res) => {
  const tenants = await tenantRepository.findAll();

  return res.status(httpStatus.OK).json({
    message: "success",
    tenants,
  });
});
