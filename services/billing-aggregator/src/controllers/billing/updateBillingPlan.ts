import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { AppDataSource } from "../../database/dataSource";
import { BillingPlanDefinitionEntity } from "../../entity/BillingPlanDefinitionEntity";

export const updateBillingPlan = asyncHandler(async (req, res) => {
  const { id } = req.params;
  const { name, label, monthlyFee, currency, description, features, popular } = req.body;

  const repo = AppDataSource.manager.getRepository(BillingPlanDefinitionEntity);
  const plan = await repo.findOne({ where: { id: Number(id) } });

  if (!plan) {
    return res.status(httpStatus.NOT_FOUND).json({ message: "Plan not found" });
  }

  if (name !== undefined) plan.name = name;
  if (label !== undefined) plan.label = label;
  if (monthlyFee !== undefined) plan.monthly_fee = monthlyFee;
  if (currency !== undefined) plan.currency = currency;
  if (description !== undefined) plan.description = description;
  if (features !== undefined) plan.features = features;
  if (popular !== undefined) plan.popular = popular;

  const saved = await repo.save(plan);
  return res.status(httpStatus.OK).json({ ...saved, monthlyFee: saved.monthly_fee });
});
