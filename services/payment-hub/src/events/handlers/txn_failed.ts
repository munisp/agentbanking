import axios from "axios";
import logger from "../../config/logger.config";
import { transactionRepository } from "../../repositories/transactionRepo";
import { ITransactionFailedEvent } from "../../types/events";
import { validateRequest } from "../../validations";
import { TxnFailedEventSchema } from "../../validations/v1/events";

export const txn_failed = async (data: ITransactionFailedEvent) => {
  try {
    logger.info(`txn_failed event: ${JSON.stringify(data)}`);

    const payload = validateRequest(TxnFailedEventSchema, data);

    await transactionRepository.failed_transaction(payload);

    const transaction = await transactionRepository.fetch_txn_record_by_txn_id(payload.transaction_id);

    if (!transaction) throw new Error("Transaction not found.");

    logger.info(`txn_failed end`);
  } catch (error) {
    logger.error("txn_failed event error:", error);
  }
};
