import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { AppDataSource } from "../../database/dataSource";
import { BillingPlanDefinitionEntity } from "../../entity/BillingPlanDefinitionEntity";

export const getBillingPlans = asyncHandler(async (_req, res) => {
  const repo = AppDataSource.manager.getRepository(BillingPlanDefinitionEntity);
  const plans = await repo.find({ where: { deleted_at: undefined }, order: { id: "ASC" } });

  return res.status(httpStatus.OK).json({ message: "success", items: plans });
});
