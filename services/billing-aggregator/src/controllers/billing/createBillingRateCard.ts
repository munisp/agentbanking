import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { AppDataSource } from "../../database/dataSource";
import { BillingRateCardEntity } from "../../entity/BillingRateCardEntity";

export const createBillingRateCard = asyncHandler(async (req, res) => {
  const repo = AppDataSource.manager.getRepository(BillingRateCardEntity);
  const card = repo.create({
    billing_account_id: req.body.billingAccountId,
    name: req.body.name,
    version: req.body.version ?? 1,
    status: req.body.status ?? "draft",
    effective_from: new Date(req.body.effectiveFrom),
    effective_to: req.body.effectiveTo ? new Date(req.body.effectiveTo) : undefined,
    pricing_currency: req.body.pricingCurrency ?? "NGN",
    created_by: req.body.createdBy ?? (req.headers["x-staff-id"] as string) ?? "system",
    approval_state: "pending",
  });
  const saved = await repo.save(card);

  return res.status(httpStatus.CREATED).json({ message: "success", item: saved });
});
