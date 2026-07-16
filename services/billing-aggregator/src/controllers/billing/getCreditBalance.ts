import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingRepository } from "../../repositories/billingRepository";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";

export const getCreditBalance = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const billing = await billingRepository.getBilling(tenant_id);

  if (!billing) {
    return res.status(httpStatus.NOT_FOUND).json({
      message: "Billing record not found",
      tenant_id,
    });
  }

  const recent_result = await billingAuditRepository.query({
    tenant_id,
    limit: 10,
    offset: 0,
  });

  const credit_transactions = recent_result.logs
    .filter((log: any) => log.action === "credit_top_up" || log.action === "payment_verified")
    .map((log: any) => ({
      date: log.created_at,
      amount: log.metadata?.amount || 0,
      reference: log.metadata?.reference,
      action: log.action,
      description: log.metadata?.description || "Credit transaction",
    }));

  return res.status(httpStatus.OK).json({
    message: "success",
    tenant_id,
    balance: billing.credits_balance,
    currency: billing.currency || "NGN",
    last_payment_date: billing.last_payment_date,
    last_payment_reference: billing.last_payment_reference,
    total_paid_ytd: billing.total_paid_ytd,
    total_outstanding: billing.total_outstanding,
    status: billing.status,
    recent_transactions: credit_transactions,
  });
});
