import httpStatus from "http-status";
import logger from "../../config/logger.config";
import { transactionRepository } from "../../repositories/transactionRepo";
import ApiError from "../../utils/ApiError";

export const reserve_txn = async (transaction_id: string) => {
  try {
    logger.info(`reserve_txn event: ${transaction_id}`);

    if (!transaction_id) {
      throw new ApiError(httpStatus.UNPROCESSABLE_ENTITY, "Invalid transaction ID");
    }

    await transactionRepository.reserve_transaction(transaction_id);

    logger.info(`reserve_txn end`);
  } catch (error) {
    logger.error("reserve_txn event error:", error);
  }
};
