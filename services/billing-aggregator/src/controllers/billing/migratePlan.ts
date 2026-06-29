import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingRepository } from "../../repositories/billingRepository";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { validateRequest, MigratePlanSchema } from "../../validations";
import { BillingAuditAction } from "../../utils/enums";

export const migratePlan = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const user_id = req.headers["x-keycloak-id"] as string;

  const input = validateRequest(MigratePlanSchema, req.body);

  const prorated_credit = input.prorate
    ? Math.round(500000 * (30 - new Date().getDate()) / 30)
    : 0;

  await billingRepository.changeBillingPlan(tenant_id, input.to_plan);

  await billingAuditRepository.record({
    tenant_id,
    user_id,
    action: BillingAuditAction.PLAN_MIGRATED,
    resource_type: "tenant_billing",
    metadata: { from: input.from_plan, to: input.to_plan, prorated_credit },
  });

  return res.status(httpStatus.OK).json({
    message: "success",
    from: input.from_plan,
    to: input.to_plan,
    prorated_credit,
  });
});
