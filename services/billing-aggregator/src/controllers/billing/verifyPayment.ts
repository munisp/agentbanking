import httpStatus from "http-status";
import { z } from "zod";
import { asyncHandler } from "../../middlewares/async";
import { getPaymentGateway } from "../../gateways";
import { validateRequest } from "../../validations";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { billingRepository } from "../../repositories/billingRepository";
import { BillingAuditAction } from "../../utils/enums";

const Schema = z.object({ reference: z.string() });

export const verifyPayment = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const user_id = req.headers["x-keycloak-id"] as string;
  const { reference } = validateRequest(Schema, req.body);

  const gateway = getPaymentGateway();
  const result = await gateway.verify(reference);

  if (result.status === "success") {
    const updated_billing = await billingRepository.updateCreditsBalance(
      tenant_id,
      result.amount,
      reference
    );

    await billingAuditRepository.record({
      tenant_id,
      user_id,
      action: BillingAuditAction.CREDIT_TOP_UP,
      resource_type: "billing_payment",
      metadata: {
        reference: result.reference,
        amount: result.amount,
        currency: result.currency,
        gateway: gateway.name,
        gateway_response: result.gateway_response,
        new_balance: updated_billing.credits_balance,
      },
    });
  } else {
    await billingAuditRepository.record({
      tenant_id,
      user_id,
      action: "payment_failed" as any,
      resource_type: "billing_payment",
      metadata: {
        reference,
        gateway: gateway.name,
        status: result.status,
      },
    });
  }

  return res.status(httpStatus.OK).json({ message: "success", ...result });
});
