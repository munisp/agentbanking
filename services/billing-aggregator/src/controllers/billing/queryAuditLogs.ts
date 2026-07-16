import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { BillingAuditAction } from "../../utils/enums";

export const queryAuditLogs = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const { action, filter_user_id, resource_type, start_date, end_date, limit, offset } =
    req.query;

  const result = await billingAuditRepository.query({
    tenant_id,
    action: action as BillingAuditAction | undefined,
    user_id: filter_user_id as string | undefined,
    resource_type: resource_type as string | undefined,
    start_date: start_date ? new Date(start_date as string) : undefined,
    end_date: end_date ? new Date(end_date as string) : undefined,
    limit: limit ? Number(limit) : 50,
    offset: offset ? Number(offset) : 0,
  });

  return res.status(httpStatus.OK).json({ message: "success", ...result });
});
