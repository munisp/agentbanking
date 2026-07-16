import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { billingLedgerRepository } from "../../repositories/billingLedgerRepository";
import { BillingModel } from "../../utils/enums";

export const queryLedger = asyncHandler(async (req, res) => {
  const tenant_id = req.headers["x-tenant-id"] as string;

  const {
    agent_id,
    billing_model,
    transaction_type,
    region,
    carrier,
    date_from,
    date_to,
    page,
    page_size,
  } = req.query;

  const result = await billingLedgerRepository.query({
    tenant_id,
    agent_id: agent_id ? Number(agent_id) : undefined,
    billing_model: billing_model as BillingModel | undefined,
    transaction_type: transaction_type as string | undefined,
    region: region as string | undefined,
    carrier: carrier as string | undefined,
    date_from: date_from ? new Date(date_from as string) : undefined,
    date_to: date_to ? new Date(date_to as string) : undefined,
    page: page ? Number(page) : 1,
    page_size: page_size ? Number(page_size) : 50,
  });

  return res.status(httpStatus.OK).json({ message: "success", ...result });
});
