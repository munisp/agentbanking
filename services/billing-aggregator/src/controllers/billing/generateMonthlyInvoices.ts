import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingLedgerRepository } from "../../repositories/billingLedgerRepository";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { billingInvoiceRepository } from "../../repositories/billingInvoiceRepository";
import { billingRepository } from "../../repositories/billingRepository";
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

  const vat_amount = platform_fee * tax.vat;
  const wht_amount = platform_fee * tax.wht;
  const total_due = platform_fee + vat_amount - wht_amount;
  const period = `${input.year}-${String(input.month).padStart(2, "0")}`;

  const preview = {
    tenant_id,
    period,
    tx_count,
    gross_volume: total_amount,
    platform_fee,
    vat_amount,
    wht_amount,
    total_due,
    status: input.dry_run ? "preview" : "generated",
  };

  if (input.dry_run) {
    return res.status(httpStatus.OK).json({
      message: "success",
      invoice_count: 1,
      total_revenue: total_due,
      invoices: [preview],
      dry_run: true,
    });
  }

  const billing = await billingRepository.findOne(tenant_id);
  const now = new Date();
  const invoice_number = `INV-${tenant_id}-${period.replace("-", "")}-${Date.now().toString(36).toUpperCase()}`;

  const invoice = await billingInvoiceRepository.create({
    tenant_id,
    invoice_number,
    plan: billing?.plan,
    period_start,
    period_end,
    subtotal: platform_fee,
    tax_rate: (tax.vat - tax.wht) * 100,
    tax_amount: vat_amount - wht_amount,
    total: total_due,
    currency: "NGN",
    due_date: new Date(now.getTime() + 30 * 24 * 60 * 60 * 1000),
    line_items: [
      { description: `Platform fee (${tx_count} transactions)`, quantity: tx_count, total: platform_fee },
      { description: "VAT", total: vat_amount },
      { description: "WHT credit", total: -wht_amount },
    ],
  });

  await billingAuditRepository.record({
    tenant_id,
    user_id,
    action: BillingAuditAction.CONFIG_UPDATED,
    resource_type: "billing_invoice",
    metadata: { period, total_due },
  });

  return res.status(httpStatus.OK).json({
    message: "success",
    invoice_count: 1,
    total_revenue: total_due,
    invoices: [invoice],
    dry_run: false,
  });
});
