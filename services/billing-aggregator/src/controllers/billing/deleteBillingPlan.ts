import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { AppDataSource } from "../../database/dataSource";
import { BillingPlanDefinitionEntity } from "../../entity/BillingPlanDefinitionEntity";

export const deleteBillingPlan = asyncHandler(async (req, res) => {
  const { id } = req.params;

  const repo = AppDataSource.manager.getRepository(BillingPlanDefinitionEntity);
  const plan = await repo.findOne({ where: { id: Number(id) } });

  if (!plan) {
    return res.status(httpStatus.NOT_FOUND).json({ message: "Plan not found" });
  }

  await repo.softDelete({ id: Number(id) });
  return res.status(httpStatus.OK).json({ message: "Plan deleted" });
});
