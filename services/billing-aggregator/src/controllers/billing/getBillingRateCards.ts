import httpStatus from "http-status";
import { asyncHandler } from "../../middlewares/async";
import { AppDataSource } from "../../database/dataSource";
import { BillingRateCardEntity } from "../../entity/BillingRateCardEntity";

export const getBillingRateCards = asyncHandler(async (_req, res) => {
  const repo = AppDataSource.manager.getRepository(BillingRateCardEntity);
  const items = await repo.find({ where: { deleted_at: undefined }, order: { id: "ASC" } });

  return res.status(httpStatus.OK).json({ asOf: new Date().toISOString(), items, total: items.length });
});
