import httpStatus from "http-status";
import { asyncHandler } from "../../../middlewares/async";
import { transactionRepository } from "../../../repositories/transactionRepo";
import ApiError from "../../../utils/ApiError";
import { validateRequest } from "../../../validations";
import { FetchTransactionStatusSchema } from "../../../validations/v1";
import { TransactionStatusEnum } from "../../../utils/enums";
import logger from "../../../config/logger.config";

export const get_transaction_details = asyncHandler(async (req, res) => {
  const payload = validateRequest(FetchTransactionStatusSchema, req);

  const transactions = await transactionRepository.fetch_txn_records_by_txn_id(
    payload.params.transaction_id,
    payload.headers.tenant
  );

  if (transactions.length === 0) {
    throw new ApiError(httpStatus.NOT_FOUND, "Transaction not found");
  }

  const responseModel = {
    status: transactions[0].status,
    amount: transactions[0].amount,
    tag: transactions[0].tag,
    is_intra: transactions.length === 2,
    completed_at:
      transactions[0].status === TransactionStatusEnum.success
        ? transactions[0].completed_at
        : undefined,
  };

  logger.info(`response_model: ${JSON.stringify(responseModel)}`);

  return res.status(200).json(responseModel);
});
