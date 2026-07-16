import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingLedgerRepository } from "../../repositories/billingLedgerRepository";

export const aggregateRevenue = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const { period, date_from, date_to } = req.query;

  const validPeriods = ["hourly", "daily", "weekly", "monthly"] as const;
  const selectedPeriod = validPeriods.includes(period as any)
    ? (period as (typeof validPeriods)[number])
    : "monthly";

  const result = await billingLedgerRepository.aggregateRevenue(
    tenant_id,
    selectedPeriod,
    date_from ? new Date(date_from as string) : undefined,
    date_to ? new Date(date_to as string) : undefined
  );

  return res.status(httpStatus.OK).json({ message: "success", ...result });
});
