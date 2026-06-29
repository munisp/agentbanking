import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { validateRequest, FileDisputeSchema } from "../../validations";
import { BillingAuditAction } from "../../utils/enums";

export const fileDispute = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const user_id = req.headers["x-keycloak-id"] as string;

  const input = validateRequest(FileDisputeSchema, req.body);

  const dispute_id = `DSP-${Date.now().toString(36).toUpperCase()}`;

  await billingAuditRepository.record({
    tenant_id,
    user_id,
    action: BillingAuditAction.DISPUTE_CREATED,
    resource_type: "billing_invoice",
    resource_id: input.invoice_id,
    metadata: { dispute_id, amount: input.amount, reason: input.reason },
  });

  return res.status(httpStatus.CREATED).json({
    message: "success",
    dispute_id,
    tenant_id,
    invoice_id: input.invoice_id,
    amount: input.amount,
    status: "open",
    created_at: new Date().toISOString(),
  });
});
