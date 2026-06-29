import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingRepository } from "../../repositories/billingRepository";
import { PutBillingPlanSchema, validateRequest } from "../../validations";

export const putBillingPlan = asyncHandler(async (req, res) => {
  const { plan } = validateRequest(PutBillingPlanSchema, req.body);

  const tenant_id = req.headers["x-tenant-id"] as string;

  await billingRepository.changeBillingPlan(tenant_id, plan);

  const billing = await billingRepository.getBilling(tenant_id);

  const billing_profile = {
    tenantId: tenant_id,
    billingInfo: {
      plan: billing?.plan,
      billingCycle: (billing?.subscription_config as any)?.billingCycle ?? "monthly",
      nextBillingDate: billing?.contract_end_date ?? null,
      status: billing?.status?.toLowerCase() ?? "active",
    },
  };

  return res.status(httpStatus.OK).json({ billing_profile });
});
