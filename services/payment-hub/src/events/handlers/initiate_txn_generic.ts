import logger from "../../config/logger.config";
import { transactionRepository } from "../../repositories/transactionRepo";
import { ITransactionInitiatedEvent } from "../../types/events";
import { validateRequest } from "../../validations";
import { TransactionInitiatedEventSchema } from "../../validations/v1/events";

export const initiate_txn_generic = async (
  data: ITransactionInitiatedEvent
) => {
  try {
    logger.info(`initiate_txn_generic event: ${JSON.stringify(data)}`);

    const payload = validateRequest(TransactionInitiatedEventSchema, data);

    await transactionRepository.create_from_generic_initiate_event(payload);

    logger.info(`initiate_txn_generic end`);
  } catch (error) {
    logger.error("initiate_txn_generic  failed:", error);
  }
};
