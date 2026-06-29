import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { billingRepository } from "../../repositories/billingRepository";
import { validateRequest, TopUpCreditsSchema } from "../../validations";
import { BillingAuditAction } from "../../utils/enums";

export const topUpCredits = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const user_id = req.headers["x-keycloak-id"] as string;

  const input = validateRequest(TopUpCreditsSchema, req.body);

  const transaction_id = `TU-${Date.now()}`;

  const updated_billing = await billingRepository.updateCreditsBalance(
    tenant_id,
    input.amount,
    transaction_id
  );

  await billingAuditRepository.record({
    tenant_id,
    user_id,
    action: BillingAuditAction.CREDIT_TOP_UP,
    resource_type: "billing_credits",
    metadata: {
      amount: input.amount,
      payment_method: input.payment_method,
      transaction_id,
      new_balance: updated_billing.credits_balance
    },
  });

  return res.status(httpStatus.OK).json({
    message: "success",
    new_balance: updated_billing.credits_balance,
    transaction_id,
    total_paid_ytd: updated_billing.total_paid_ytd,
  });
});
