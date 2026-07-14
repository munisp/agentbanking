import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { AppDataSource } from "../../database/dataSource";
import { TenantBillingEntity } from "../../entity/TenantBillingEntity";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { validateRequest, RenewContractSchema } from "../../validations";
import { BillingAuditAction } from "../../utils/enums";
import { ApiError } from "../../middlewares/error";

export const renewContract = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const user_id = req.headers["x-keycloak-id"] as string;

  const input = validateRequest(RenewContractSchema, req.body);

  const billing = await AppDataSource.manager.findOne(TenantBillingEntity, {
    where: { tenant_id },
  });

  if (!billing) throw new ApiError(httpStatus.NOT_FOUND, "Billing config not found");

  const before_state = { contract_end_date: billing.contract_end_date, auto_renew: billing.auto_renew };

  billing.contract_end_date = new Date(input.new_end_date);
  billing.auto_renew = true;
  await AppDataSource.manager.save(billing);

  await billingAuditRepository.record({
    tenant_id,
    user_id,
    action: BillingAuditAction.CONTRACT_RENEWED,
    resource_type: "tenant_billing",
    resource_id: String(billing.id),
    before_state,
    after_state: { contract_end_date: input.new_end_date, auto_renew: true },
  });

  return res.status(httpStatus.OK).json({
    message: "success",
    tenant_id,
    new_end_date: input.new_end_date,
    status: "renewed",
  });
});
