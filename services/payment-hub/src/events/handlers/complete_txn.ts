import logger from "../../config/logger.config";
import { transactionRepository } from "../../repositories/transactionRepo";
import { ITransactionCompletedEvent } from "../../types/events";
import { validateRequest } from "../../validations";
import { TxnCompletedEventSchema } from "../../validations/v1/events";

export const complete_txn = async (data: ITransactionCompletedEvent) => {
  try {
    logger.info(`complete_txn event: ${JSON.stringify(data)}`);

    const payload = validateRequest(TxnCompletedEventSchema, data);

    await transactionRepository.complete_txn(payload);

    logger.info(`complete_txn end`);
  } catch (error) {
    logger.error("complete_txn failed:", error);
    throw error;
  }
};
