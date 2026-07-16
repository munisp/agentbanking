import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { BillingAuditAction } from "../../utils/enums";

export const exportAuditCsv = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const user_id = req.headers["x-keycloak-id"] as string;

  const { start_date, end_date } = req.query;

  if (!start_date || !end_date) {
    return res.status(400).json({ message: "start_date and end_date are required" });
  }

  const logs = await billingAuditRepository.queryForExport(
    tenant_id,
    new Date(start_date as string),
    new Date(end_date as string)
  );

  const header = "id,tenant_id,user_id,user_name,action,resource_type,resource_id,created_at\n";
  const rows = logs
    .map(
      (l) =>
        `${l.id},${l.tenant_id},${l.user_id},"${l.user_name ?? ""}",${l.action},${l.resource_type ?? ""},${l.resource_id ?? ""},${l.created_at}`
    )
    .join("\n");

  await billingAuditRepository.record({
    tenant_id,
    user_id,
    action: BillingAuditAction.EXPORT_GENERATED,
    resource_type: "billing_audit_log",
    metadata: { start_date, end_date, row_count: logs.length },
  });

  return res.status(httpStatus.OK).json({
    message: "success",
    csv: header + rows,
    row_count: logs.length,
  });
});
