import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { AppDataSource } from "../../database/dataSource";
import { TenantBillingEntity } from "../../entity/TenantBillingEntity";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { validateRequest, SuspendBillingSchema } from "../../validations";
import { BillingAuditAction, BillingStatus } from "../../utils/enums";
import { ApiError } from "../../middlewares/error";

export const suspendBilling = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const user_id = req.headers["x-keycloak-id"] as string;

  const input = validateRequest(SuspendBillingSchema, req.body);

  const billing = await AppDataSource.manager.findOne(TenantBillingEntity, {
    where: { tenant_id },
  });

  if (!billing) throw new ApiError(httpStatus.NOT_FOUND, "Billing config not found");

  billing.status = BillingStatus.SUSPENDED;
  await AppDataSource.manager.save(billing);

  await billingAuditRepository.record({
    tenant_id,
    user_id,
    action: BillingAuditAction.BILLING_SUSPENDED,
    resource_type: "tenant_billing",
    resource_id: String(billing.id),
    after_state: { status: BillingStatus.SUSPENDED, reason: input.reason },
  });

  return res.status(httpStatus.OK).json({
    message: "success",
    tenant_id,
    status: "suspended",
    reason: input.reason,
  });
});
