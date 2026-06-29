import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { BillingAuditAction } from "../../utils/enums";

export const exportInvoices = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const user_id = req.headers["x-keycloak-id"] as string;

  const { start_date, end_date, format = "csv" } = req.query;

  await billingAuditRepository.record({
    tenant_id,
    user_id,
    action: BillingAuditAction.EXPORT_GENERATED,
    resource_type: "billing_invoice",
    metadata: { start_date, end_date, format },
  });

  const download_url = `/api/billing/export/${tenant_id}/${format}?start=${start_date}&end=${end_date}`;

  return res.status(httpStatus.OK).json({
    message: "success",
    download_url,
    expires_at: new Date(Date.now() + 3600000).toISOString(),
  });
});
