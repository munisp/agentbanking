import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingRepository } from "../../repositories/billingRepository";

const DUNNING_SCHEDULE = [
  { day: 1, action: "reminder_email", severity: "low", description: "Gentle payment reminder" },
  { day: 3, action: "sms_reminder", severity: "low", description: "SMS payment reminder" },
  { day: 7, action: "warning_email", severity: "medium", description: "Final warning before service degradation" },
  { day: 14, action: "service_degradation", severity: "high", description: "Reduced service availability" },
  { day: 30, action: "account_suspension", severity: "critical", description: "Account suspended" },
  { day: 90, action: "account_termination", severity: "critical", description: "Account terminated, data archived" },
];

export const getDunningStatus = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const dunning_status = await billingRepository.getDunningStatus(tenant_id);

  let current_step = 0;
  if (dunning_status.total_outstanding > 0 && !dunning_status.has_grace_period) {
    const days_since_payment = dunning_status.last_payment_date
      ? Math.floor((Date.now() - dunning_status.last_payment_date.getTime()) / (1000 * 60 * 60 * 24))
      : 0;

    for (let i = DUNNING_SCHEDULE.length - 1; i >= 0; i--) {
      if (days_since_payment >= DUNNING_SCHEDULE[i].day) {
        current_step = i;
        break;
      }
    }
  }

  return res.status(httpStatus.OK).json({
    message: "success",
    tenant_id,
    dunning_schedule: DUNNING_SCHEDULE,
    current_step,
    current_action: current_step >= 0 ? DUNNING_SCHEDULE[current_step] : null,
    grace_period_days: dunning_status.grace_days_remaining,
    grace_period_reason: dunning_status.grace_period_reason,
    has_grace_period: dunning_status.has_grace_period,
    outstanding_amount: dunning_status.total_outstanding,
    credits_balance: dunning_status.credits_balance,
    total_paid_ytd: dunning_status.total_paid_ytd,
    last_payment_date: dunning_status.last_payment_date,
  });
});
