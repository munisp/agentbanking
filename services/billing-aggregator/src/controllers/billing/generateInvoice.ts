import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingLedgerRepository } from "../../repositories/billingLedgerRepository";
import { billingInvoiceRepository } from "../../repositories/billingInvoiceRepository";
import { billingRepository } from "../../repositories/billingRepository";
import { validateRequest, GenerateInvoiceSchema } from "../../validations";
import { BillingModel } from "../../utils/enums";
import { BillingLedgerEntity } from "../../entity/BillingLedgerEntity";

function padTwo(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

export const generateInvoice = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const input = validateRequest(GenerateInvoiceSchema, req.body);

  const period_start = new Date(input.period_start);
  const period_end = new Date(input.period_end);

  const config = await billingLedgerRepository.getClientBillingConfig(tenant_id);

  const qb_result = await billingLedgerRepository.query({
    tenant_id,
    date_from: period_start,
    date_to: period_end,
    page_size: 10000,
  });

  const entries: BillingLedgerEntity[] = qb_result.entries;
  const tx_count = entries.length;
  const total_gross_fees = entries.reduce((s: number, e: BillingLedgerEntity) => s + Number(e.gross_fee), 0);
  const total_platform_share = entries.reduce((s: number, e: BillingLedgerEntity) => s + Number(e.platform_revenue), 0);
  const total_switch_fee = entries.reduce((s: number, e: BillingLedgerEntity) => s + Number(e.switch_fee), 0);
  const total_agent_commission = entries.reduce((s: number, e: BillingLedgerEntity) => s + Number(e.agent_commission), 0);

  const tax_rate = input.tax_rate ?? 7.5;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const line_items: any[] = [
    {
      description: `Transaction processing fees (${tx_count} transactions)`,
      quantity: tx_count,
      unit_price: tx_count > 0 ? total_gross_fees / tx_count : 0,
      total: total_gross_fees,
      category: "transaction_fee",
    },
    {
      description: "Platform revenue share",
      quantity: 1,
      unit_price: total_platform_share,
      total: total_platform_share,
      category: "transaction_fee",
    },
    {
      description: "Switch/network fees",
      quantity: 1,
      unit_price: total_switch_fee,
      total: total_switch_fee,
      category: "transaction_fee",
    },
    {
      description: "Agent commissions",
      quantity: 1,
      unit_price: total_agent_commission,
      total: total_agent_commission,
      category: "transaction_fee",
    },
  ];

  if (
    config.billing_model === BillingModel.SUBSCRIPTION ||
    config.billing_model === BillingModel.HYBRID
  ) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const sub_config = config.subscription_config as any;
    if (sub_config?.perAgentFee) {
      const agent_count = sub_config.agentCount ?? 10;
      line_items.push({
        description: "Monthly agent subscription",
        quantity: agent_count,
        unit_price: sub_config.perAgentFee,
        total: agent_count * sub_config.perAgentFee,
        category: "subscription",
      });
    }
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const subtotal = line_items.reduce((s: number, item: any) => s + item.total, 0);
  const tax_amount = subtotal * (tax_rate / 100);
  const total = subtotal + tax_amount;
  const now = new Date();
  const invoice_number = `INV-${tenant_id}-${now.getFullYear()}${padTwo(now.getMonth() + 1)}-${Date.now().toString(36).toUpperCase()}`;

  const billing = await billingRepository.findOne(tenant_id);
  const due_date = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000);

  const invoice = await billingInvoiceRepository.create({
    tenant_id,
    invoice_number,
    plan: billing?.plan,
    period_start,
    period_end,
    subtotal,
    tax_rate,
    tax_amount,
    total,
    currency: input.currency ?? "NGN",
    due_date,
    line_items,
  });

  return res.status(httpStatus.CREATED).json({ message: "success", invoice });
});
