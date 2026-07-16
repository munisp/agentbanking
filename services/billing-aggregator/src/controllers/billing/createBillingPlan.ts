import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { AppDataSource } from "../../database/dataSource";
import { BillingPlanDefinitionEntity } from "../../entity/BillingPlanDefinitionEntity";

export const createBillingPlan = asyncHandler(async (req, res) => {
  const { name, label, monthlyFee, currency, description, features, popular } = req.body;

  if (!name || !label) {
    return res.status(httpStatus.BAD_REQUEST).json({ message: "name and label are required" });
  }

  const repo = AppDataSource.manager.getRepository(BillingPlanDefinitionEntity);

  const plan = repo.create({
    name,
    label,
    monthly_fee: monthlyFee ?? 0,
    currency: currency ?? "NGN",
    description,
    features: features ?? [],
    popular: popular ?? false,
  });

  const saved = await repo.save(plan);
  return res.status(httpStatus.CREATED).json({ ...saved, monthlyFee: saved.monthly_fee });
});
