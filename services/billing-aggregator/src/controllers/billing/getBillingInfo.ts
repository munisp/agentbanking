import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingRepository } from "../../repositories/billingRepository";

export const getBillingInfo = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const billing = await billingRepository.getBilling(tenant_id);

  const billing_info = {
    plan: billing?.plan ?? null,
    billingCycle: (billing?.subscription_config as any)?.billingCycle ?? "monthly",
    nextBillingDate: billing?.contract_end_date ?? null,
    status: billing?.status?.toLowerCase() ?? "active",
  };

  return res.status(httpStatus.OK).json({ billing_info });
});
