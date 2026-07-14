import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";

export const getAuditSummary = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const days = req.query.days ? Number(req.query.days) : 30;
  const summary = await billingAuditRepository.getSummary(tenant_id, days);

  return res.status(httpStatus.OK).json({ message: "success", ...summary });
});
