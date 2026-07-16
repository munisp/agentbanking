import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingRepository } from "../../repositories/billingRepository";
import { billingInvoiceRepository, toInvoiceDto } from "../../repositories/billingInvoiceRepository";

export const getBillingDashboard = asyncHandler(async (_req, res) => {
  const [billing, invoices] = await Promise.all([
    billingRepository.findAll(),
    billingInvoiceRepository.findAll(),
  ]);

  // Rows from before billing-aggregator adopted tenant_id as its join key are
  // permanently orphaned (see BackfillTenantId1747008000000) — not real tenants.
  const accounts = billing.filter((b) => b.tenant_id).map((b) => ({
    id: b.id,
    tenantId: b.tenant_id,
    // no tenant-name join available cross-service — fall back to tenant_id
    accountName: b.tenant_id,
    plan: b.plan,
    currency: b.currency,
    status: b.status?.toLowerCase(),
    billingPeriod: (b.subscription_config as { billingCycle?: string } | undefined)?.billingCycle ?? "monthly",
    contractEndAt: b.contract_end_date,
  }));

  return res.status(httpStatus.OK).json({
    message: "success",
    accounts,
    invoices: invoices.map(toInvoiceDto),
  });
});
