import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { billingRepository } from "../../repositories/billingRepository";
import { validateRequest, ApplyGracePeriodSchema } from "../../validations";
import { BillingAuditAction } from "../../utils/enums";

export const applyGracePeriod = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const user_id = req.headers["x-keycloak-id"] as string;

  const input = validateRequest(ApplyGracePeriodSchema, req.body);

  const updated_billing = await billingRepository.applyGracePeriod(
    tenant_id,
    input.days,
    input.reason
  );

  const grace_period_end = updated_billing.grace_period_end?.toISOString() || "";

  await billingAuditRepository.record({
    tenant_id,
    user_id,
    action: BillingAuditAction.GRACE_PERIOD_APPLIED,
    resource_type: "tenant_billing",
    metadata: {
      days: input.days,
      reason: input.reason,
      grace_period_end,
      action_type: "grace_period_applied"
    },
  });

  return res.status(httpStatus.OK).json({
    message: "success",
    grace_period_end,
    days: input.days,
    reason: input.reason,
    applied_at: new Date().toISOString(),
  });
});
