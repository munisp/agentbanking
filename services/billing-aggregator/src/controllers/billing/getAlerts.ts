import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingRepository } from "../../repositories/billingRepository";
import { BillingStatus } from "../../utils/enums";

export const getAlerts = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const billing = await billingRepository.getBilling(tenant_id);
  const alerts: any[] = [];
  const now = new Date();

  if (!billing) {
    return res.status(httpStatus.OK).json({ message: "success", alerts });
  }

  if (
    billing.contract_end_date &&
    new Date(billing.contract_end_date) < new Date(Date.now() + 30 * 24 * 60 * 60 * 1000)
  ) {
    const days_left = Math.ceil(
      (billing.contract_end_date.getTime() - now.getTime()) / (1000 * 60 * 60 * 24)
    );
    alerts.push({
      id: "alert_contract_expiry",
      severity: days_left <= 7 ? "critical" : "warning",
      title: "Contract expiring soon",
      message: `Contract ends in ${days_left} days (${new Date(billing.contract_end_date).toLocaleDateString()})`,
      created_at: new Date().toISOString(),
      action_url: "/settings/billing/renew",
    });
  }

  if (billing.grace_period_end && billing.grace_period_end > now) {
    const days_left = Math.ceil((billing.grace_period_end.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    alerts.push({
      id: "alert_grace_period_active",
      severity: "warning",
      title: "Grace period active",
      message: `Grace period ends in ${days_left} days. Reason: ${billing.grace_period_reason || "Payment pending"}`,
      created_at: new Date().toISOString(),
      action_url: "/billing/payment",
    });
  }

  if (billing.credits_balance < 10000) {
    alerts.push({
      id: "alert_low_credits",
      severity: billing.credits_balance === 0 ? "critical" : "warning",
      title: billing.credits_balance === 0 ? "No credits available" : "Low credits balance",
      message: `Current balance: ${billing.credits_balance} ${billing.currency || "NGN"}. Please top up to continue transactions.`,
      created_at: new Date().toISOString(),
      action_url: "/billing/topup",
    });
  }

  if (billing.total_outstanding > 0) {
    alerts.push({
      id: "alert_outstanding_balance",
      severity: billing.total_outstanding > 100000 ? "critical" : "warning",
      title: "Outstanding balance due",
      message: `You have ${billing.total_outstanding} ${billing.currency || "NGN"} outstanding. Please make payment.`,
      created_at: new Date().toISOString(),
      action_url: "/billing/payment",
    });
  }

  if (
    billing.status === BillingStatus.ACTIVE &&
    billing.total_outstanding > 0 &&
    !billing.grace_period_end
  ) {
    const days_last_payment = billing.last_payment_date
      ? Math.floor((now.getTime() - billing.last_payment_date.getTime()) / (1000 * 60 * 60 * 24))
      : 999;

    if (days_last_payment >= 14) {
      alerts.push({
        id: "alert_suspension_risk",
        severity: "critical",
        title: "Account suspension risk",
        message: `No payment in ${days_last_payment} days. Account may be suspended. Please make payment immediately.`,
        created_at: new Date().toISOString(),
        action_url: "/billing/payment",
      });
    }
  }

  if (billing.status === BillingStatus.SUSPENDED) {
    alerts.push({
      id: "alert_suspended",
      severity: "critical",
      title: "Account suspended",
      message: "Your account has been suspended due to non-payment. Contact support to reactivate.",
      created_at: new Date().toISOString(),
      action_url: "/support/contact",
    });
  }

  return res.status(httpStatus.OK).json({
    message: "success",
    alerts: alerts.sort((a: any, b: any) => {
      const severity_order: Record<string, number> = { critical: 0, warning: 1, info: 2 };
      return (severity_order[a.severity] || 3) - (severity_order[b.severity] || 3);
    }),
  });
});
