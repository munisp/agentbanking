import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";

export const getResourceHistory = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const { resource_type, resource_id } = req.query;

  if (!resource_type || !resource_id) {
    return res.status(400).json({ message: "resource_type and resource_id are required" });
  }

  const result = await billingAuditRepository.getResourceHistory(
    tenant_id,
    resource_type as string,
    resource_id as string
  );

  return res.status(httpStatus.OK).json({ message: "success", ...result });
});
