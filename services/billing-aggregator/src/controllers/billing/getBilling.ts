import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingRepository } from "../../repositories/billingRepository";

export const getBilling = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const billing = await billingRepository.getBilling(tenant_id);

  return res.status(httpStatus.OK).json({
    message: "success",
    billing,
  });
});
