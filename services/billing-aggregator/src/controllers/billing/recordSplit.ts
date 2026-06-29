import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingLedgerRepository } from "../../repositories/billingLedgerRepository";
import { billingAuditRepository } from "../../repositories/billingAuditRepository";
import { validateRequest, RecordSplitSchema } from "../../validations";

export const recordSplit = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;
  const user_id = req.headers["x-keycloak-id"] as string;

  const input = validateRequest(RecordSplitSchema, req.body);

  const entry = await billingLedgerRepository.recordSplit({ ...input, tenant_id });

  const kafkaUrl = process.env.KAFKA_BROKER_URL;
  if (kafkaUrl) {
    console.log(`[BillingLedger] Kafka publish: billing.ledger.splits`, { entry_id: entry.id });
  }

  await billingAuditRepository.record({
    tenant_id,
    user_id,
    action: "split_recorded" as any,
    resource_type: "billing_ledger",
    resource_id: String(entry.id),
    after_state: {
      transaction_ref: entry.transaction_ref,
      gross_fee: entry.gross_fee,
      billing_model: entry.billing_model,
    },
  });

  return res.status(httpStatus.CREATED).json({ message: "success", entry });
});
