import { ApiError } from "../middlewares/error";
import * as z from "zod";
import httpStatus from "http-status";
import logger from "../config/logger.config";
import { BillingModel, BillingPlan, BillingRole } from "../utils/enums";

export function validateRequest<T>(schema: z.ZodType<T>, payload: object) {
  try {
    schema.parse(payload);
    return payload as z.infer<typeof schema>;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
  } catch (e: any) {
    logger.error("Validation error: %o", e);
    throw new ApiError(httpStatus.UNPROCESSABLE_ENTITY, e.message ?? "Validation error");
  }
}

export const PutBillingPlanSchema = z.object({
  plan: z.nativeEnum(BillingPlan),
});

// ─── Billing Ledger ───────────────────────────────────────────────────────────

export const RecordSplitSchema = z.object({
  transaction_ref: z.string(),
  transaction_type: z.string().optional(),
  agent_id: z.number(),
  pos_terminal_id: z.number().optional(),
  gross_amount: z.number(),
  gross_fee: z.number(),
  agent_commission: z.number(),
  switch_fee: z.number(),
  aggregator_fee: z.number().optional(),
  billing_model: z.nativeEnum(BillingModel),
  revenue_share_pct: z.number().optional(),
  currency: z.string().optional(),
  region: z.string().optional(),
  carrier: z.string().optional(),
});

// ─── Invoice ─────────────────────────────────────────────────────────────────

export const GenerateInvoiceSchema = z.object({
  period_start: z.string(),
  period_end: z.string(),
  currency: z.string().optional(),
  tax_rate: z.number().optional(),
});

export const MarkPaidSchema = z.object({
  payment_ref: z.string(),
  paid_at: z.string().optional(),
});

export const GenerateCreditNoteSchema = z.object({
  amount: z.number(),
  reason: z.string(),
});

// ─── RBAC ─────────────────────────────────────────────────────────────────────

export const AssignBillingRoleSchema = z.object({
  user_id: z.string(),
  billing_role: z.nativeEnum(BillingRole),
  custom_permissions: z.array(z.string()).optional(),
  expires_at: z.string().datetime().optional(),
});

// ─── Lifecycle ────────────────────────────────────────────────────────────────

export const RenewContractSchema = z.object({
  new_end_date: z.string(),
});

export const SuspendBillingSchema = z.object({
  reason: z.string(),
  suspend_until: z.string().optional(),
});

export const TerminateContractSchema = z.object({
  reason: z.string(),
  effective_date: z.string(),
});

export const FileDisputeSchema = z.object({
  invoice_id: z.string(),
  amount: z.number(),
  reason: z.string(),
  evidence: z.string().optional(),
});

export const ResolveDisputeSchema = z.object({
  resolution: z.enum(["approved", "rejected", "partial"]),
  adjustment_amount: z.number().optional(),
  notes: z.string(),
});

// ─── Production ───────────────────────────────────────────────────────────────

export const GenerateMonthlyInvoicesSchema = z.object({
  month: z.number().min(1).max(12),
  year: z.number(),
  dry_run: z.boolean().optional(),
});

export const ApplyGracePeriodSchema = z.object({
  days: z.number().min(1).max(30),
  reason: z.string(),
});

export const TriggerReconciliationSchema = z.object({
  date_range: z.object({ start: z.string(), end: z.string() }),
  type: z.enum(["full", "incremental", "spot_check"]),
});

export const MigratePlanSchema = z.object({
  from_plan: z.nativeEnum(BillingPlan),
  to_plan: z.nativeEnum(BillingPlan),
  prorate: z.boolean().optional(),
});

export const TopUpCreditsSchema = z.object({
  amount: z.number().min(100000),
  payment_method: z.string(),
});

export const GenerateComplianceReportSchema = z.object({
  report_type: z.enum(["cbn_returns", "firs_vat", "firs_wht", "annual_audit", "aml_sar"]),
  period: z.object({ start: z.string(), end: z.string() }),
  format: z.enum(["json", "csv", "pdf"]).optional(),
});
