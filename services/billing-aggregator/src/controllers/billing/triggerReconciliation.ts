import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { AppDataSource } from "../../database/dataSource";
import { BillingReconciliationReportEntity } from "../../entity/BillingReconciliationReportEntity";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { validateRequest, TriggerReconciliationSchema } from "../../validations";
import { BillingAuditAction, ReconciliationStatus } from "../../utils/enums";

export const triggerReconciliation = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const user_id = req.headers["x-keycloak-id"] as string;

  const input = validateRequest(TriggerReconciliationSchema, req.body);

  const report = AppDataSource.manager.create(BillingReconciliationReportEntity, {
    tenant_id,
    report_period: input.type,
    period_start: new Date(input.date_range.start),
    period_end: new Date(input.date_range.end),
    status: ReconciliationStatus.IN_PROGRESS,
    generated_by: user_id,
  });
  const saved_report = await AppDataSource.manager.save(report);

  await billingAuditRepository.record({
    tenant_id,
    user_id,
    action: BillingAuditAction.RECONCILIATION_RUN,
    resource_type: "billing_reconciliation_report",
    resource_id: String(saved_report.id),
    metadata: { type: input.type, date_range: input.date_range },
  });

  return res.status(httpStatus.OK).json({
    message: "success",
    workflow_id: `recon-${saved_report.id}-${Date.now()}`,
    report_id: saved_report.id,
    status: "started",
    type: input.type,
  });
});
