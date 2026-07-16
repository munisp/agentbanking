import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { getPaymentGateway } from "../../gateways";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { billingRepository } from "../../repositories/billingRepository";
import { BillingAuditAction } from "../../utils/enums";
import logger from "../../config/logger.config";

export const paymentWebhook = asyncHandler(async (req, res) => {
  const gateway = getPaymentGateway();

  const signature =
    (req.headers["stripe-signature"] as string) ??
    (req.headers["x-paystack-signature"] as string) ??
    (req.headers["verif-hash"] as string) ??
    "";

  const rawBody = JSON.stringify(req.body);

  if (!gateway.validateWebhook(rawBody, signature)) {
    logger.warn(`Invalid webhook signature from ${gateway.name}`);
    return res.status(httpStatus.UNAUTHORIZED).json({ message: "invalid signature" });
  }

  const event = req.body;

  const isSuccess =
    event.event === "charge.success" ||
    (event.event === "charge.completed" && event.data?.status === "successful");

  if (isSuccess) {
    const data = event.data ?? {};
    const reference = data.reference ?? data.tx_ref ?? "";
    const amount = data.amount ? (gateway.name === "paystack" ? data.amount / 100 : data.amount) : 0;
    const tenant_id: string = data.metadata?.tenant_id ?? data.meta?.tenant_id ?? "unknown";

    logger.info(`Payment success via ${gateway.name}: ref=${reference} amount=${amount} tenant=${tenant_id}`);

    try {
      const updated_billing = await billingRepository.updateCreditsBalance(tenant_id, amount, reference);

      await billingAuditRepository.record({
        tenant_id,
        user_id: "webhook",
        action: BillingAuditAction.CREDIT_TOP_UP,
        resource_type: "billing_payment",
        metadata: {
          reference,
          amount,
          gateway: gateway.name,
          event: event.event,
          new_balance: updated_billing.credits_balance,
        },
      });

      logger.info(`Credit updated for tenant ${tenant_id}: new balance = ${updated_billing.credits_balance}`);
    } catch (err: any) {
      logger.error(`Failed to update credits for tenant ${tenant_id}: ${err.message}`);
    }
  }

  return res.status(httpStatus.OK).json({ message: "received" });
});
