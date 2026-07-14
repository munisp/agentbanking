import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingLedgerRepository } from "../../repositories/billingLedgerRepository";

export const getClientBillingConfig = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const config = await billingLedgerRepository.getClientBillingConfig(tenant_id);

  return res.status(httpStatus.OK).json({ message: "success", config });
});
