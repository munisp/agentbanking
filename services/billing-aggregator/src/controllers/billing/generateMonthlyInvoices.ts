import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingLedgerRepository } from "../../repositories/billingLedgerRepository";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { validateRequest, GenerateMonthlyInvoicesSchema } from "../../validations";
import { BillingAuditAction } from "../../utils/enums";

const TAX_JURISDICTIONS: Record<string, { vat: number; wht: number; stamp: number }> = {
  NG_FEDERAL: { vat: 0.075, wht: 0.10, stamp: 0.005 },
  NG_LAGOS: { vat: 0.075, wht: 0.10, stamp: 0.005 },
  GH_ACCRA: { vat: 0.125, wht: 0.08, stamp: 0.005 },
  KE_NAIROBI: { vat: 0.16, wht: 0.05, stamp: 0.002 },
};

export const generateMonthlyInvoices = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const user_id = req.headers["x-keycloak-id"] as string;

  const input = validateRequest(GenerateMonthlyInvoicesSchema, req.body);

  const period_start = new Date(input.year, input.month - 1, 1);
  const period_end = new Date(input.year, input.month, 0, 23, 59, 59);

  const ledger_result = await billingLedgerRepository.query({
    tenant_id,
    date_from: period_start,
    date_to: period_end,
    page_size: 100000,
  });

  const entries = ledger_result.entries;
  const total_amount = entries.reduce((s, e) => s + Number(e.gross_amount), 0);
  const tx_count = entries.length;
  const platform_fee = total_amount * 0.30;
  const tax = TAX_JURISDICTIONS["NG_FEDERAL"];

  const invoice = {
    tenant_id,
    period: `${input.year}-${String(input.month).padStart(2, "0")}`,
    tx_count,
    gross_volume: total_amount,
    platform_fee,
    vat_amount: platform_fee * tax.vat,
    wht_amount: platform_fee * tax.wht,
    total_due: platform_fee + platform_fee * tax.vat - platform_fee * tax.wht,
    status: input.dry_run ? "preview" : "generated",
  };

  if (!input.dry_run) {
    await billingAuditRepository.record({
      tenant_id,
      user_id,
      action: BillingAuditAction.CONFIG_UPDATED,
      resource_type: "billing_invoice",
      metadata: { period: invoice.period, total_due: invoice.total_due },
    });
  }

  return res.status(httpStatus.OK).json({
    message: "success",
    invoice_count: 1,
    total_revenue: invoice.total_due,
    invoices: [invoice],
    dry_run: input.dry_run ?? false,
  });
});
