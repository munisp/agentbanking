import logger from "../../config/logger.config";
import { transactionRepository } from "../../repositories/transactionRepo";
import { IUpdateLocalTxnIdEvent } from "../../types/events";
import { validateRequest } from "../../validations";
import { UpdateLocalTxnIdEventSchema } from "../../validations/v1/events";

export const update_local_txn_id = async (data: IUpdateLocalTxnIdEvent) => {
  try {
    logger.info(`update_local_txn_id event: ${JSON.stringify(data)}`);

    const payload = validateRequest(UpdateLocalTxnIdEventSchema, data);

    await transactionRepository.update_local_txn_id(payload);

    logger.info(`update_local_txn_id end`);
  } catch (error) {
    logger.error("update_local_txn_id failed:", error);
  }
};
