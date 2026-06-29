import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";

const SLA_TIERS: Record<string, { uptimePct: number; responseMs: number; compensationPct: number }> = {
  platinum: { uptimePct: 99.99, responseMs: 100, compensationPct: 25 },
  gold: { uptimePct: 99.95, responseMs: 250, compensationPct: 15 },
  silver: { uptimePct: 99.9, responseMs: 500, compensationPct: 10 },
  bronze: { uptimePct: 99.5, responseMs: 1000, compensationPct: 5 },
};

export const getSlaMetrics = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const period = (req.query.period as string) ?? "month";

  return res.status(httpStatus.OK).json({
    message: "success",
    tenant_id,
    period,
    sla_tier: "gold",
    sla_config: SLA_TIERS.gold,
    current_metrics: {
      uptime_pct: 99.97,
      avg_response_ms: 180,
      p99_response_ms: 420,
      reconciliation_accuracy_pct: 99.8,
      invoice_delivery_on_time_pct: 100,
    },
    sla_targets: {
      uptime_pct: 99.9,
      avg_response_ms: 250,
      reconciliation_accuracy_pct: 99.5,
    },
    breaches: [],
    sla_compliant: true,
  });
});
